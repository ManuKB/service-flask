# FastAPI -> Flask conversion guide

This is a port of `C:\Users\mohan\OneDrive\Documents\Iromind\Service` (a FastAPI
household-management API) to Flask, living in a sibling directory
`C:\Users\mohan\OneDrive\Documents\Iromind\service-flask`.

**`Service/` is READ-ONLY reference material. Do not create, edit, or delete
anything under `Service/` for any reason.** Everything you write goes under
`service-flask/`.

## What already exists (read these first - they're your pattern to mirror)

The shared core and one full reference vertical (auth/families/invitations)
are already converted and working:

- `service-flask/app/core/config.py` - same pydantic-settings Settings class, unchanged.
- `service-flask/app/core/database.py` - sync SQLAlchemy engine/Session. `get_db()` returns the request-scoped `Session` (backed by `flask.g`, opened/closed in `app/main.py`).
- `service-flask/app/core/security.py` - copied verbatim from Service (already sync - JWT + bcrypt hashing).
- `service-flask/app/core/status.py` - numeric HTTP status constants under the same dotted names FastAPI's `status` module used (`status.HTTP_404_NOT_FOUND` etc.) so you can keep writing `status.HTTP_XXX` unchanged.
- `service-flask/app/core/exceptions.py` - defines `AppError(status_code, detail)`, the Flask equivalent of FastAPI's `HTTPException(status_code, detail)`. Raise it exactly the same way.
- `service-flask/app/core/deps.py` - `get_current_user_id()` and `get_current_user()` - call these as plain functions (no `Depends(...)` wrapper - Flask doesn't have FastAPI's dependency injection).
- `service-flask/app/core/responses.py` - `envelope(model, status_code=200)`, `envelope_list(models, status_code=200)`, `no_content()` - use these to return pydantic models as JSON, replacing FastAPI's automatic `response_model=` serialization.
- `service-flask/app/modules/permissions/rbac.py` - `get_membership(db, family_id, user_id)`, `require_active_member(db, family_id, user_id)`, `require_owner(db, family_id, user_id)` - same names as before, now called explicitly instead of via `Depends(...)`.
- `service-flask/app/modules/permissions/roles.py` - copied verbatim (plain enums, no framework dependency).
- `service-flask/app/modules/audit/service.py` + `router.py` + `permissions.py` - full reference conversion.
- `service-flask/app/modules/auth/service.py` + `router.py` - full reference conversion (see how request bodies, path params, and error handling look end to end).
- `service-flask/app/modules/families/service.py` + `router.py` - full reference conversion, including a local (function-body) import to break a circular-import cycle with invitations - same pattern the FastAPI version used.
- `service-flask/app/modules/invitations/*.py` - full reference conversion.
- `service-flask/app/modules/notifications/service.py` + `router.py` - full reference conversion (does NOT include `notifications/push/` - that's a separate workstream happening in parallel; see below).
- `service-flask/app/models/*` and `service-flask/app/schemas/*` - copied **verbatim, unchanged** from `Service/app/models` and `Service/app/schemas`. These are framework-agnostic (plain SQLAlchemy declarative models / plain pydantic `BaseModel`s with no FastAPI imports) so they needed zero changes. **Do not modify them** - if your module needs a new schema field, that would be surprising; there shouldn't be a need to touch these for this conversion.
- `service-flask/app/main.py` - the Flask app factory (`create_app()`). It already has `app.register_blueprint(...)` lines for every module, including yours - **you do not need to touch `main.py`**. Every router module just needs to expose a module-level `bp` blueprint object with the exact name shown in the import list in `main.py` (e.g. `from app.modules.finance.accounts.router import bp as finance_accounts_bp`).
- `service-flask/requirements.txt` - already installed into `service-flask/.venv`. If your module needs something not listed, add it to `requirements.txt` too and install it into that venv with:
  `C:/Users/mohan/OneDrive/Documents/Iromind/service-flask/.venv/Scripts/python.exe -m pip install <package>`

## Mechanical conversion rules

### Service files (`service.py`)

1. Remove every `async def` -> `def`. Remove every `await ` (the keyword and the trailing space).
2. `from sqlalchemy.ext.asyncio import AsyncSession` -> `from sqlalchemy.orm import Session`. Every type hint `db: AsyncSession` -> `db: Session`.
3. All the SQLAlchemy call shapes are identical between sync and async minus the `await` - `db.scalar(select(...))`, `db.scalars(select(...))`, `db.execute(...)`, `db.get(Model, id)`, `db.add(...)`, `db.add_all(...)`, `db.delete(...)`, `db.flush()`, `db.commit()`, `db.refresh(...)`, `db.rollback()` all exist on the sync `Session` with the same names and arguments.
4. Custom `*Error` exception classes (e.g. `FamilyError`, `AuthError`) - keep them exactly as-is, they're just plain `Exception` subclasses.
5. If your module calls into another module's service functions (e.g. finance calling `notifications_service.notify_user(...)`, or calendar calling `push_service.send_web_push_to_user(...)`), those functions are/will also be sync in the Flask version - just drop the `await` at the call site, same as everywhere else.
6. Pure-logic helper files with **no** `async def`/`await` in them at all (verify with a quick grep first) can be copied byte-for-byte unchanged with `cp` - no edits needed. Files with a couple of `async def`/`await` scattered in an otherwise sync-looking file (e.g. a small `NotificationSender`/`ReminderSender` ABC-based stub class) just need those two keywords removed, nothing else.

### Router files (`router.py`)

FastAPI's automatic request/response handling has no Flask equivalent, so
routers need more manual work than services. Compare
`service-flask/app/modules/families/router.py` side by side with
`Service/app/modules/families/router.py` for the fullest example (query
params, path params, multiple dependencies, request bodies, and both single
and list responses). The mechanical shape is:

| FastAPI | Flask |
|---|---|
| `router = APIRouter(prefix="/x", tags=[...])` | `bp = Blueprint("x", __name__, url_prefix="/x")` |
| `@router.get("/{id}")` | `@bp.get("/<uuid:id>")` (Flask's built-in `uuid` converter parses the same way FastAPI's `id: uuid.UUID` param did) |
| `@router.post("", status_code=status.HTTP_201_CREATED)` | `@bp.post("")` - pass the status code to `envelope(...)` at the return, see below |
| `payload: SomeRequest` (body) | `payload = SomeRequest(**request.get_json(force=True))` (needs `from flask import request`) |
| `month: str = Query(pattern=...)` | `month = request.args.get("month")` - validate/parse manually (e.g. reuse `dateutils.parse_month`, which already raises `ValueError` - catch it and `raise AppError(status.HTTP_400_BAD_REQUEST, str(exc))`) |
| `user_id: uuid.UUID = Depends(get_current_user_id)` | `user_id = get_current_user_id()` (called inside the function body) |
| `db: AsyncSession = Depends(get_db)` | `db = get_db()` |
| `_membership = Depends(require_active_member)` | `require_active_member(db, family_id, user_id)` (call db/get_current_user_id first, then this) |
| `raise HTTPException(status.HTTP_404_NOT_FOUND, "msg")` | `raise AppError(status.HTTP_404_NOT_FOUND, "msg")` (same import style: `from app.core import status`, `from app.core.exceptions import AppError`) |
| `return some_orm_object` with `response_model=XResponse` | `return envelope(XResponse.model_validate(some_orm_object))` |
| `return [orm_objects]` with `response_model=list[XResponse]` | `return envelope_list([XResponse.model_validate(o) for o in orm_objects])` |
| success status other than 200 | `return envelope(XResponse.model_validate(obj), status.HTTP_201_CREATED)` |
| `status_code=status.HTTP_204_NO_CONTENT` with no return value | `return no_content()` |
| Function already returning a manually-constructed schema instance (not from an ORM object) | `return envelope(SomeResponse(field=value, ...))` - same pattern, `model_validate` isn't needed when you're building the schema instance by hand |

Every route handler needs the `bp` decorator, e.g.:

```python
from flask import Blueprint, request

from app.core import status
from app.core.database import get_db
from app.core.deps import get_current_user_id
from app.core.exceptions import AppError
from app.core.responses import envelope, envelope_list, no_content
from app.modules.permissions.rbac import require_active_member
from app.modules.yourmodule import service
from app.schemas.yourmodule import YourResponse, YourCreateRequest

bp = Blueprint("yourmodule", __name__, url_prefix="/families/<uuid:family_id>/yourmodule")


@bp.post("")
def create_thing(family_id):
    user_id = get_current_user_id()
    db = get_db()
    require_active_member(db, family_id, user_id)
    payload = YourCreateRequest(**request.get_json(force=True))
    try:
        thing = service.create_thing(db, family_id, payload.name)
    except service.YourModuleError as exc:
        raise AppError(status.HTTP_409_CONFLICT, str(exc)) from exc
    return envelope(YourResponse.model_validate(thing), status.HTTP_201_CREATED)
```

Note the `url_prefix` can itself contain a Flask path converter
(`<uuid:family_id>`) when every route in that blueprint is nested under a
family, exactly like the notifications router does it - see
`service-flask/app/modules/notifications/router.py`.

### A signature you can depend on before it exists

Push notifications (`service-flask/app/modules/notifications/push/`) are
being built by a different workstream in parallel. If your module's
converted `service.py` needs to call it (mirroring the original FastAPI code
that did `await push_service.send_web_push_to_user(...)`), assume this exact
sync signature and call it normally - it will exist by the time everything
is wired together:

```python
from app.modules.notifications.push import service as push_service

push_service.send_web_push_to_user(db, notification.user_id, title, body)  # -> None
```

## Self-check before you finish

Verify every router module you wrote imports cleanly, using the project's
own venv (don't use any other Python):

```
C:/Users/mohan/OneDrive/Documents/Iromind/service-flask/.venv/Scripts/python.exe -c "from app.modules.yourmodule.router import bp; print('ok')"
```

Run this from `C:/Users/mohan/OneDrive/Documents/Iromind/service-flask` (it
needs to be the working directory so the `app` package resolves and `.env`
loads). A few of your modules will legitimately fail this check until the
*other* parallel workstreams finish (e.g. anything importing
`notifications.push.service` before that file exists, or `calendar`/`tasks`
importing each other) - that's expected and fine; just make sure the
failure is an `ImportError` pointing at a file **outside** your own module,
not a syntax error or bug inside code you wrote.
