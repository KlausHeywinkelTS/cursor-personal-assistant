"""MCP-Schnittstelle (Streamable HTTP) für Claude Code. Servername `team`.

In Claude Code heißen die Werkzeuge mcp__team__list_agents usw. (Punkte wie in `team.list_agents`
erlaubt das Namensschema nicht).

Die Identität des aufrufenden Subagenten kennt nur der PreToolUse-Hook (agent_id). Der Hook legt
tool_use_id -> agent_id in der Brücke ab. Der MCP-Aufruf trägt dieselbe tool_use_id im _meta
(`claudecode/toolUseId`). Ohne Brückeneintrag gilt der Aufrufer als unbekannt und kann nichts ändern.

Es gibt bewusst kein Werkzeug, mit dem ein Agent andere Agenten beauftragt.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import anyio
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from .bridge import ToolUseBridge
from .config import Settings
from .errors import ServiceError
from .service import TaskService

TOOL_USE_ID_KEY = "claudecode/toolUseId"


def tool_use_id_from_meta(meta: Any) -> str | None:
    if meta is None:
        return None
    if isinstance(meta, dict):
        value = meta.get(TOOL_USE_ID_KEY)
    else:
        value = (getattr(meta, "model_extra", None) or {}).get(TOOL_USE_ID_KEY)
    return str(value) if value else None


def build_mcp(service: TaskService, bridge: ToolUseBridge, settings: Settings) -> FastMCP:
    mcp = FastMCP(
        "team",
        instructions=(
            "Auftragsverwaltung für das Agententeam. Der beauftragte Agent meldet Fortschritt (update_task), "
            "Blocker (report_blocker) und Ergebnis (complete_task) mit der ihm zugewiesenen task_id."
        ),
        host=settings.host,
        port=settings.port,
        streamable_http_path="/mcp",
        stateless_http=True,  # robust gegen Neustarts und mehrere gleichzeitige Fenster
    )

    async def caller(ctx: Context) -> str | None:
        meta = ctx.request_context.meta
        return await bridge.resolve(tool_use_id_from_meta(meta), settings.bridge_wait_s)

    async def run(fn: Callable[[], Any]) -> Any:
        try:
            return await anyio.to_thread.run_sync(fn)
        except ServiceError as exc:
            raise ToolError(str(exc)) from exc

    @mcp.tool()
    async def list_agents() -> list[dict]:
        """Listet alle Agenten mit Verfügbarkeit (available/busy) und aktuellem Auftrag."""
        return await run(service.list_agents)

    @mcp.tool()
    async def start_task(agent: str, title: str, description: str = "", project_path: str = "") -> dict:
        """Reserviert einen Agenten und legt einen Auftrag an. Lehnt ab, wenn der Agent bereits einen aktiven Auftrag hat."""
        return await run(lambda: service.start_task(agent, title, description, project_path or None))

    @mcp.tool()
    async def get_task(task_id: int) -> dict:
        """Liefert alle Details eines Auftrags samt Ereignisprotokoll."""
        return await run(lambda: service.get_task(task_id))

    @mcp.tool()
    async def update_task(ctx: Context, task_id: int, status: str = "", message: str = "") -> dict:
        """Meldet Fortschritt (message). status darf leer oder IN_PROGRESS sein (nach einem gelösten Blocker)."""
        agent_id = await caller(ctx)
        return await run(lambda: service.agent_update(agent_id, task_id, status, message))

    @mcp.tool()
    async def complete_task(ctx: Context, task_id: int, summary: str, result_reference: str = "") -> dict:
        """Meldet den Auftrag als abgeschlossen. Er geht in REVIEW_REQUIRED, erst der Benutzer setzt DONE."""
        agent_id = await caller(ctx)
        return await run(lambda: service.agent_complete(agent_id, task_id, summary, result_reference or None))

    @mcp.tool()
    async def report_blocker(ctx: Context, task_id: int, reason: str) -> dict:
        """Meldet, dass die Arbeit blockiert ist und eine Entscheidung des Benutzers benötigt wird."""
        agent_id = await caller(ctx)
        return await run(lambda: service.agent_blocker(agent_id, task_id, reason))

    return mcp
