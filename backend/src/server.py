from __future__ import annotations

import uuid

from flask import Flask, g, request
from flask_cors import CORS

from src.catalog.loader import load_catalog
from src.routes import register_routes
from src.shared.errors import register_error_handlers


def create_app() -> Flask:
    app = Flask(__name__)
    CORS(app)

    load_catalog()

    @app.before_request
    def attach_request_id() -> None:
        incoming = request.headers.get("X-Request-Id", "").strip()
        g.request_id = incoming or f"req_{uuid.uuid4().hex[:12]}"

    @app.after_request
    def add_request_id_header(response):
        request_id = getattr(g, "request_id", None)
        if request_id:
            response.headers["X-Request-Id"] = request_id
        return response

    register_routes(app)
    register_error_handlers(app)

    return app