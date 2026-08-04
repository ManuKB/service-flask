from flask import Response, jsonify
from pydantic import BaseModel

# FastAPI serialized responses automatically via `response_model=...`. Flask
# routes do it explicitly with these two helpers - `mode="json"` makes
# pydantic render UUID/datetime/Decimal etc. as JSON-safe primitives first,
# so the plain `jsonify()` afterwards never chokes on a non-JSON-native type.


def envelope(model: BaseModel, status_code: int = 200) -> tuple[Response, int]:
    return jsonify(model.model_dump(mode="json")), status_code


def envelope_list(models: list[BaseModel], status_code: int = 200) -> tuple[Response, int]:
    return jsonify([m.model_dump(mode="json") for m in models]), status_code


def no_content() -> tuple[str, int]:
    return "", 204
