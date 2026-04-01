"""
Filter a Teams message export JSON by date range and print to stdout.

Usage:
    py filter_messages.py <json_file> <from_date> <to_date>

Dates are inclusive and in format YYYY-MM-DD.

Output: filtered JSON sorted chronologically (oldest first), printed to stdout.
"""

import json
import sys
from datetime import datetime, timezone


def parse_date(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def parse_created_at(s: str) -> datetime:
    s = s.rstrip("Z")
    # Handle optional fractional seconds
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date: {s}")


def collect(messages: list, from_dt: datetime, to_dt: datetime) -> list:
    """Recursively collect all messages (including replies) within the date range."""
    result = []
    for msg in messages:
        created = msg.get("created-at")
        if created:
            ts = parse_created_at(created)
            if from_dt <= ts <= to_dt:
                entry = {k: v for k, v in msg.items() if k != "replies"}
                replies_in_range = collect(msg.get("replies", []), from_dt, to_dt)
                if replies_in_range:
                    entry["replies"] = replies_in_range
                result.append(entry)
    return result


def main():
    if len(sys.argv) != 4:
        print("Usage: py filter_messages.py <json_file> <from_date> <to_date>", file=sys.stderr)
        sys.exit(1)

    json_file, from_str, to_str = sys.argv[1], sys.argv[2], sys.argv[3]

    from_dt = parse_date(from_str)
    to_dt = parse_date(to_str).replace(hour=23, minute=59, second=59)

    with open(json_file, encoding="utf-8") as f:
        messages = json.load(f)

    filtered = collect(messages, from_dt, to_dt)
    filtered.sort(key=lambda m: m.get("created-at", ""))

    print(json.dumps(filtered, ensure_ascii=False, indent=2))
    print(f"\n[{len(filtered)} top-level messages in range {from_str} – {to_str}]", file=sys.stderr)


if __name__ == "__main__":
    main()
