"""Phase-1-Spike: Mini-MCP-Server (Streamable HTTP) für V4.

Zeigt, welche Request-Header und Argumente ein MCP-Server von Claude Code tatsächlich sieht.
Läuft auf 127.0.0.1:8798, Endpunkt /mcp. Log: spike/mcp_log.jsonl
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from mcp.server.fastmcp import Context, FastMCP

LOG = Path(__file__).parent / "mcp_log.jsonl"

mcp = FastMCP("spike-team", host="127.0.0.1", port=8798)


@mcp.tool()
def ping(task_id: str, ctx: Context) -> str:
    """Spike-Tool: protokolliert, was der Server über den Aufrufer erfährt."""
    request = ctx.request_context.request
    headers = dict(request.headers) if request is not None else {}
    headers.pop("authorization", None)
    record = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "tool": "ping",
        "task_id": task_id,
        "headers": headers,
        "meta": str(getattr(ctx.request_context, "meta", None)),
    }
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return f"pong {task_id}"


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
