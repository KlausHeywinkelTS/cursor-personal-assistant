"""
Extract Team ID + Channel ID (for channel links) or Chat ID (for chat links)
from a Microsoft Teams URL.
"""

import sys
from urllib.parse import urlparse, parse_qs, unquote, quote


def extract_ids(url: str) -> dict:
    parsed = urlparse(url)

    if parsed.netloc != "teams.microsoft.com":
        raise ValueError("Not a valid Microsoft Teams URL.")

    # Path segments after URL-decoding
    path_parts = [p for p in parsed.path.split("/") if p]
    # Expected structure: ['l', 'channel'|'chat', <id>, ...]

    if len(path_parts) < 3 or path_parts[0] != "l":
        raise ValueError("Unexpected URL path structure.")

    link_type = path_parts[1]

    if link_type == "channel":
        channel_id = quote(unquote(path_parts[2]), safe=":_-.")
        query_params = parse_qs(parsed.query)
        group_ids = query_params.get("groupId", [])
        if not group_ids:
            raise ValueError("groupId (Team ID) not found in URL.")
        team_id = group_ids[0]
        return {
            "type": "channel",
            "team_id": team_id,
            "channel_id": channel_id,
        }

    elif link_type == "chat":
        chat_id = quote(unquote(path_parts[2]), safe=":_-.")
        return {
            "type": "chat",
            "chat_id": chat_id,
        }

    else:
        raise ValueError(f"Unsupported Teams link type: '{link_type}'.")


def main():
    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        url = input("Paste the Teams link: ").strip()

    result = extract_ids(url)

    if result["type"] == "channel":
        print("\nChannel link detected:")
        print(f"  Team ID    : {result['team_id']}")
        print(f"  Channel ID : {result['channel_id']}")
    else:
        print("\nChat link detected:")
        print(f"  Chat ID : {result['chat_id']}")


if __name__ == "__main__":
    main()
