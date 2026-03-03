from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from flask import Flask, g, jsonify


@dataclass
class ApiError(Exception):
    code: str
    message: str
    status_code: int
    details: list[dict[str, str]] | None = None


class ValidationError(ApiError):
    def __init__(self, message: str, details: list[dict[str, str]] | None = None):
        super().__init__(
            code="VALIDATION_ERROR",
            message=message,
            status_code=400,
            details=details,
        )


class NotImplementedErrorApi(ApiError):
    def __init__(self, message: str):
        super().__init__(
            code="NOT_IMPLEMENTED",
            message=message,
            status_code=501,
        )


class NotFoundError(ApiError):
    def __init__(self, message: str):
        super().__init__(
            code="NOT_FOUND",
            message=message,
            status_code=404,
        )


def build_error_response(
    *,
    code: str,
    message: str,
    status_code: int,
    details: list[dict[str, str]] | None = None,
):
    request_id = getattr(g, "request_id", None)
    payload: dict[str, Any] = {
        "error": {
            "code": code,
            "message": message,
        }
    }

    if details:
        payload["error"]["details"] = details

    if request_id:
        payload["error"]["requestId"] = request_id

    return jsonify(payload), status_code


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(ApiError)
    def _handle_api_error(err: ApiError):
        return build_error_response(
            code=err.code,
            message=err.message,
            status_code=err.status_code,
            details=err.details,
        )

    @app.errorhandler(Exception)
    def _handle_unexpected(_: Exception):
        return build_error_response(
            code="INTERNAL_ERROR",
            message="Unexpected server error",
            status_code=500,
        )