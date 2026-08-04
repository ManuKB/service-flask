from flask import Flask, jsonify
from pydantic import ValidationError
from werkzeug.exceptions import HTTPException


class AppError(Exception):
    """HTTP-status-carrying error - the Flask equivalent of FastAPI's
    `HTTPException(status_code, detail)`. Routers raise this exactly the way
    the FastAPI version raised HTTPException; the registered error handler
    below turns it into the same `{"detail": ...}` JSON shape."""

    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(AppError)
    def _handle_app_error(exc: AppError):
        return jsonify({"detail": exc.detail}), exc.status_code

    @app.errorhandler(ValidationError)
    def _handle_validation_error(exc: ValidationError):
        # Mirrors FastAPI's automatic 422 for a body that fails schema validation.
        return jsonify({"detail": exc.errors(include_url=False, include_context=False)}), 422

    @app.errorhandler(HTTPException)
    def _handle_http_exception(exc: HTTPException):
        # Werkzeug's own routing errors (404 for an unmatched route, 405 for
        # a wrong method, etc.) - pass the real status through unchanged.
        return jsonify({"detail": exc.description}), exc.code

    @app.errorhandler(Exception)
    def _handle_unhandled_exception(exc: Exception):
        app.logger.exception("Unhandled exception")
        return jsonify({"detail": "Internal server error"}), 500
