"""Eindeutige Fehlercodes und Ausnahmen des Services."""

from __future__ import annotations

from enum import StrEnum


class ErrorCode(StrEnum):
    AGENT_BUSY = "AGENT_BUSY"
    AGENT_UNKNOWN = "AGENT_UNKNOWN"
    TASK_NOT_FOUND = "TASK_NOT_FOUND"
    INVALID_TRANSITION = "INVALID_TRANSITION"
    NOT_TASK_OWNER = "NOT_TASK_OWNER"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    INVALID_INPUT = "INVALID_INPUT"


class ServiceError(Exception):
    """Basisklasse: trägt einen Fehlercode, eine verständliche Meldung und optionale Details."""

    code: ErrorCode = ErrorCode.INVALID_INPUT
    http_status: int = 400

    def __init__(self, message: str, *, code: ErrorCode | None = None, details: dict | None = None):
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        self.details = details or {}

    def as_dict(self) -> dict:
        return {"code": str(self.code), "message": self.message, "details": self.details}

    def __str__(self) -> str:  # für MCP-Tool-Fehler: Code vorn, damit er maschinenlesbar bleibt
        return f"{self.code}: {self.message}"


class AgentBusy(ServiceError):
    code = ErrorCode.AGENT_BUSY
    http_status = 409


class AgentUnknown(ServiceError):
    code = ErrorCode.AGENT_UNKNOWN
    http_status = 404


class TaskNotFound(ServiceError):
    code = ErrorCode.TASK_NOT_FOUND
    http_status = 404


class InvalidTransition(ServiceError):
    code = ErrorCode.INVALID_TRANSITION
    http_status = 409


class NotTaskOwner(ServiceError):
    code = ErrorCode.NOT_TASK_OWNER
    http_status = 403


class Unauthorized(ServiceError):
    code = ErrorCode.UNAUTHORIZED
    http_status = 401


class Forbidden(ServiceError):
    code = ErrorCode.FORBIDDEN
    http_status = 403
