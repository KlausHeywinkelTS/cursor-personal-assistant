"""Schutz der lokalen HTTP-Schnittstelle.

- Host-Prüfung gegen DNS-Rebinding (nur 127.0.0.1:PORT und localhost:PORT).
- Bearer-Token für Hook- und MCP-Endpunkte.
- Cockpit-Schreibaktionen: Origin + CSRF-Token (kein Bearer-Token, siehe require_cockpit_write). Es gibt keine
  CORS-Freigabe, fremde Webseiten können Antworten weder lesen noch den benutzerdefinierten Header setzen.
  Grenze: Ein lokaler Prozess mit Benutzerrechten kann Origin und CSRF-Token nachbauen. Das Modell schützt
  vor Webseiten, nicht vor beliebigem lokalem Code.
"""

from __future__ import annotations

import hmac
import json
import secrets

from fastapi import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from .errors import ErrorCode, Forbidden, Unauthorized

PROTECTED_PREFIXES = ("/hooks", "/mcp")


def _header(scope: Scope, name: bytes) -> str:
    for key, value in scope.get("headers", []):
        if key == name:
            return value.decode("latin-1")
    return ""


async def _reject(send: Send, status: int, code: ErrorCode, message: str) -> None:
    body = json.dumps({"error": {"code": str(code), "message": message, "details": {}}}).encode()
    await send({"type": "http.response.start", "status": status,
                "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]})
    await send({"type": "http.response.body", "body": body})


class HostCheckMiddleware:
    def __init__(self, app: ASGIApp, allowed_hosts: set[str]) -> None:
        self.app, self.allowed = app, {h.lower() for h in allowed_hosts}

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and _header(scope, b"host").lower() not in self.allowed:
            await _reject(send, 403, ErrorCode.FORBIDDEN, "Ungültiger Host-Header (nur lokaler Zugriff erlaubt).")
            return
        await self.app(scope, receive, send)


class BearerAuthMiddleware:
    def __init__(self, app: ASGIApp, token: str) -> None:
        self.app, self.token = app, token

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["path"].startswith(PROTECTED_PREFIXES):
            if not valid_bearer(_header(scope, b"authorization"), self.token):
                await _reject(send, 401, ErrorCode.UNAUTHORIZED, "Fehlendes oder ungültiges Token.")
                return
        await self.app(scope, receive, send)


def valid_bearer(header: str, token: str) -> bool:
    scheme, _, value = header.partition(" ")
    return scheme.lower() == "bearer" and hmac.compare_digest(value.strip().encode(), token.encode())


def new_csrf_token() -> str:
    return secrets.token_urlsafe(24)


def require_cockpit_write(request: Request) -> None:
    """Dependency für schreibende Cockpit-Endpunkte."""
    # Bewusst KEIN Bearer-Token: Es steht in der Umgebung der Claude-Code-Sessions (Hooks) und wäre damit
    # für Agenten lesbar. Sonst könnte ein Agent per curl seinen eigenen Review auf DONE setzen.
    state = request.app.state
    allowed_origins = {f"http://{h}" for h in state.settings.allowed_hosts}
    origin = request.headers.get("origin", "")
    if origin not in allowed_origins:
        raise Forbidden("Ungültiger oder fehlender Origin-Header.")
    if not hmac.compare_digest(request.headers.get("x-csrf-token", "").encode(), state.csrf_token.encode()):
        raise Unauthorized("Ungültiges CSRF-Token.")
