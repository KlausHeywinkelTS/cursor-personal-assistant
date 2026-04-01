"""
Call the Power Automate webhook to request a Teams message export.

The webhook receives a JSON payload with the extracted IDs and the desired
output filename, then asynchronously writes the result to OneDrive.

Configuration is loaded from config.toml in the project root.
The environment variable TEAMS_WEBHOOK_URL overrides the webhook URL in the config.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

import requests

from get_teams_ids import extract_ids

# ---------------------------------------------------------------------------
# Load config.toml
# ---------------------------------------------------------------------------

_CONFIG_PATH = Path(__file__).parent.parent / "config.toml"

try:
    if sys.version_info >= (3, 11):
        import tomllib
    else:
        try:
            import tomli as tomllib  # pip install tomli
        except ImportError:
            tomllib = None  # type: ignore[assignment]

    if tomllib is None:
        raise ImportError

    if _CONFIG_PATH.exists():
        with open(_CONFIG_PATH, "rb") as _f:
            _config = tomllib.load(_f)
    else:
        print(f"Warning: config.toml not found at {_CONFIG_PATH}. Using built-in defaults.")
        _config = {}

except ImportError:
    print(
        "Warning: TOML support not available (requires Python 3.11+ or: pip install tomli). "
        "Using built-in defaults."
    )
    _config = {}

# ---------------------------------------------------------------------------
# Settings — config.toml values, with hard-coded fallback defaults
# ---------------------------------------------------------------------------

_export_cfg = _config.get("export", {})
_webhook_cfg = _config.get("webhook", {})

DOCS_DIR: str = _export_cfg.get(
    "output_dir",
    r"C:\Users\Kl6713\OneDrive - Trusted Shops AG\Dokumente",
)
POLL_INTERVAL_S: int = _export_cfg.get("poll_interval_seconds", 5)
MAX_WAIT_S: int = _export_cfg.get("max_wait_seconds", 300)

# Environment variable takes precedence over config file value
WEBHOOK_URL: str = (
    os.environ.get("TEAMS_WEBHOOK_URL")
    or _webhook_cfg.get("url", "")
)


def postprocess_chat_json(file_path: str) -> None:
    with open(file_path, encoding="utf-8") as f:
        messages = json.load(f)

    by_id = {msg["id"]: msg for msg in messages if "id" in msg}

    top_level = []
    for msg in messages:
        parent_id = msg.get("replyTo")
        if parent_id and parent_id in by_id:
            parent = by_id[parent_id]
            parent.setdefault("replies", []).append(msg)
        else:
            top_level.append(msg)

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(top_level, f, ensure_ascii=False, indent=2)

    reply_count = len(messages) - len(top_level)
    print(f"Post-processing done: {len(top_level)} top-level messages, {reply_count} replies nested.")


def build_payload(result: dict, output_file: str, message_count: int) -> dict:
    if result["type"] == "channel":
        return {
            "teamId": result["team_id"],
            "channelId": result["channel_id"],
            "chatId": "",
            "outputFile": output_file,
            "loops": message_count,
        }
    else:
        return {
            "teamId": "",
            "channelId": "",
            "chatId": result["chat_id"],
            "outputFile": output_file,
            "loops": message_count,
        }


def main():
    parser = argparse.ArgumentParser(description="Request a Teams message export via Power Automate webhook.")
    parser.add_argument("--url", required=True, help="Full Teams channel or chat link.")
    parser.add_argument("--output", default="export", help="Base name of the output file (default: export).")
    parser.add_argument("--loops", type=int, default=2, help="Number of fetch loops; each loop retrieves 5 messages (default: 10).")
    args = parser.parse_args()

    result = extract_ids(args.url)

    if result["type"] == "channel":
        print(f"  Team ID    : {result['team_id']}")
        print(f"  Channel ID : {result['channel_id']}")
    else:
        print(f"  Chat ID : {result['chat_id']}")

    # --- Output filename ---
    timestamp_ms = int(time.time() * 1000)
    base = args.output[:-5] if args.output.endswith(".json") else args.output
    export_type = "channel" if result["type"] == "channel" else "chat"
    output_file = f"{base}_{export_type}_{timestamp_ms}.json"

    # --- Call webhook ---
    payload = build_payload(result, output_file, args.loops)
    print(f"\nSending request to webhook ...")
    print(f"  Payload: {payload}")

    response = requests.post(WEBHOOK_URL, json=payload, timeout=30)
    response.raise_for_status()

    print(f"\nWebhook responded with status {response.status_code}.")
    print(f"Waiting for '{output_file}' to appear in {DOCS_DIR} ...")

    output_path = os.path.join(DOCS_DIR, output_file)
    deadline = time.time() + MAX_WAIT_S
    while time.time() < deadline:
        if os.path.isfile(output_path):
            print(f"\nFile created: {output_path}")
            postprocess_chat_json(output_path)
            break
        remaining = int(deadline - time.time())
        print(f"  Not yet available, retrying in {POLL_INTERVAL_S}s (timeout in {remaining}s) ...")
        time.sleep(POLL_INTERVAL_S)
    else:
        print(f"\nTimeout: file was not created within {MAX_WAIT_S} seconds.")


if __name__ == "__main__":
    main()
