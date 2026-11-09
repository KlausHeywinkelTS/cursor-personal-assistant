"""FastAPI-Anwendung: Hooks, MCP, Cockpit-API und statische Oberfläche in einem Prozess."""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path

import anyio
from fastapi import Body, Depends, FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import __version__
from .bridge import ToolUseBridge
from .config import Settings
from .db import Database
from .errors import ServiceError
from .events_bus import EventBus
from .hooks import HookHandler
from .mcp_server import build_mcp
from .notify import Notifier, NullNotifier, SystemNotifier
from .profiles import load_profiles
from .security import BearerAuthMiddleware, HostCheckMiddleware, new_csrf_token, require_cockpit_write
from .service import USER_ACTIONS, TaskService

log = logging.getLogger("team_manager.app")
STATIC_DIR = Path(__file__).parent / "static"


class ActionBody(BaseModel):
    note: str = ""


def sync_profiles(service: TaskService, settings: Settings) -> list[str]:
    """Liest die Agentenprofile, gleicht die Tabelle ab und schreibt den Cache für den Gate-Hook."""
    profiles = load_profiles(settings.agents_dir)
    service.sync_agents(profiles)
    names = service.team_agent_names()
    settings.ensure_home()
    tmp = settings.team_agents_cache.with_suffix(".tmp")
    tmp.write_text(json.dumps({"names": names}), encoding="utf-8")
    tmp.replace(settings.team_agents_cache)
    log.info("profiles_synced", extra={"agents": names, "dir": str(settings.agents_dir)})
    return names


async def _watchdog_loop(service: TaskService, interval: float) -> None:
    while True:
        await asyncio.sleep(interval)
        try:
            changed = await anyio.to_thread.run_sync(service.run_watchdog)
            if changed:
                log.info("watchdog_changed", extra={"task_ids": changed})
        except Exception:
            log.exception("watchdog_failed")


def create_app(settings: Settings | None = None, *, notifier: Notifier | None = None) -> FastAPI:
    settings = settings or Settings()
    token = settings.load_token()
    db = Database(settings.db_path)
    db.migrate()
    bus, bridge = EventBus(), ToolUseBridge()
    if notifier is None:
        notifier = SystemNotifier() if settings.notifications else NullNotifier()
    service = TaskService(db, settings, notifier=notifier, bus=bus)
    sync_profiles(service, settings)
    handler = HookHandler(service, bridge, cockpit_url=f"http://127.0.0.1:{settings.port}")
    mcp = build_mcp(service, bridge, settings)
    mcp_app = mcp.streamable_http_app()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        watchdog = asyncio.create_task(_watchdog_loop(service, settings.watchdog_interval_s))
        try:
            async with mcp.session_manager.run():
                log.info("service_started", extra={"port": settings.port, "version": __version__})
                yield
        finally:
            watchdog.cancel()

    app = FastAPI(title="Team Manager", version=__version__, lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.settings, app.state.token, app.state.csrf_token = settings, token, new_csrf_token()
    app.state.service, app.state.bridge, app.state.bus, app.state.hooks = service, bridge, bus, handler

    @app.exception_handler(ServiceError)
    async def service_error(_: Request, exc: ServiceError) -> JSONResponse:
        return JSONResponse({"error": exc.as_dict()}, status_code=exc.http_status)

    # ------------------------------------------------------------------ Claude-Code-Hooks

    @app.post("/hooks")
    def hooks(payload: dict = Body(...)) -> dict:
        return handler.handle(payload)

    # ------------------------------------------------------------------ Cockpit-API

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok", "version": __version__, "agents": service.team_agent_names()}

    @app.get("/api/csrf")
    def csrf(request: Request) -> JSONResponse:
        return JSONResponse({"csrf_token": request.app.state.csrf_token}, headers={"Cache-Control": "no-store"})

    @app.get("/api/state")
    def state() -> JSONResponse:
        return JSONResponse(service.snapshot(), headers={"Cache-Control": "no-store"})

    @app.get("/api/tasks")
    def tasks(filter: str = "all") -> list[dict]:
        return service.list_tasks(filter)

    @app.get("/api/tasks/{task_id}")
    def task_detail(task_id: int) -> dict:
        return service.get_task(task_id, events=200)

    @app.post("/api/tasks/{task_id}/actions/{action}", dependencies=[Depends(require_cockpit_write)])
    def task_action(task_id: int, action: str, body: ActionBody | None = None) -> dict:
        if action not in USER_ACTIONS:
            raise ServiceError(f"Unbekannte Aktion '{action}'.")
        service.user_action(task_id, action, (body.note if body else ""))
        return service.get_task(task_id, events=200)

    @app.get("/api/stream")
    async def stream(request: Request) -> StreamingResponse:
        async def events():
            async with bus.subscribe() as queue:
                yield "retry: 3000\n\nevent: hello\ndata: {}\n\n"
                while not await request.is_disconnected():
                    try:
                        event = await asyncio.wait_for(queue.get(), timeout=15)
                        yield f"event: changed\ndata: {json.dumps(event)}\n\n"
                    except TimeoutError:
                        yield ": keepalive\n\n"

        return StreamingResponse(
            events(), media_type="text/event-stream", headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"}
        )

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html", headers={"Cache-Control": "no-store"})

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    # Zuletzt: alles Übrige (insbesondere /mcp) geht an den MCP-Server.
    app.mount("/", mcp_app)

    # Middleware: zuletzt hinzugefügt = äußerste Schicht. Host-Prüfung vor allem anderen.
    app.add_middleware(BearerAuthMiddleware, token=token)
    app.add_middleware(HostCheckMiddleware, allowed_hosts=settings.allowed_hosts)
    return app
