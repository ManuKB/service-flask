# INOVERA Family - backend (Flask port)

This is a Flask port of the FastAPI backend in the sibling `Service/`
directory. Same routes, same request/response shapes, same SQLite database
schema and file (`inovera.db`) - only the web framework and the async ->
sync database layer changed. `Service/` was left completely untouched;
nothing here modifies it.

See `CONVERSION_GUIDE.md` for the conversion rules this port followed.

## What changed vs. the FastAPI original

- **Sync everywhere.** FastAPI + `AsyncSession` (`aiosqlite`) -> Flask +
  plain SQLAlchemy `Session` (`sqlite3`). Every `service.py` function lost
  its `async`/`await`; the SQL call shapes (`db.scalar`, `db.get`, `db.add`,
  `db.commit`, ...) are otherwise identical.
- **No dependency injection.** FastAPI's `Depends(get_db)` /
  `Depends(get_current_user_id)` / `Depends(require_active_member)` are now
  plain functions called explicitly at the top of each route
  (`app/core/deps.py`, `app/modules/permissions/rbac.py`).
- **Manual request/response handling.** Request bodies are parsed as
  `SomeSchema(**request.get_json(force=True))`; responses are built with
  `envelope()`/`envelope_list()`/`no_content()` (`app/core/responses.py`)
  instead of FastAPI's automatic `response_model=`. Pydantic schemas
  themselves are unchanged (copied verbatim from `Service/app/schemas`).
- **`AppError` replaces `HTTPException`.** Same `(status_code, detail)`
  shape, same `{"detail": ...}` JSON error body - see
  `app/core/exceptions.py`.
- **Background scheduler is a daemon thread**, not an `asyncio.Task` (Flask/
  WSGI has no event loop) - see `app/core/scheduler.py`.
- **Models and schemas are untouched copies.** Neither
  `Service/app/models/*` nor `Service/app/schemas/*` import anything
  FastAPI-specific, so they needed zero changes.

## Module map (identical routes/ownership to the FastAPI version)

| Module | Mounted at | Owns |
|---|---|---|
| `app.modules.auth` | `/auth` | User, RefreshToken, PasswordSetupToken |
| `app.modules.families` | `/families` | Family, FamilyMembership |
| `app.modules.invitations` | `/families/*/invitations`, `/invitations` | Invitation |
| `app.modules.audit` | `/families/*/audit` | AuditEvent |
| `app.modules.finance.accounts` | `/families/*/finance/accounts` | Account |
| `app.modules.finance.categories` | `/families/*/finance/categories` | Category |
| `app.modules.finance.transactions` | `/families/*/finance/transactions` | Transaction |
| `app.modules.finance.budgets` | `/families/*/finance/budgets` | Budget |
| `app.modules.finance.bills` | `/families/*/finance/bills` | RecurringBill, BillCompletion |
| `app.modules.finance.overview` | `/families/*/finance/overview` | (aggregation only) |
| `app.modules.calendar.calendars` | `/families/*/calendar/calendars` | Calendar |
| `app.modules.calendar.events` | `/families/*/calendar/events` | Event, EventParticipant |
| `app.modules.calendar.agenda` | `/families/*/calendar/agenda` | (expansion only) |
| `app.modules.calendar.reminders` | `/families/*/calendar/events/*/reminders` | Reminder |
| `app.modules.notifications` | `/families/*/notifications` | Notification |
| `app.modules.notifications.push` | `/push` | PushSubscription |
| `app.modules.tasks` | `/families/*/tasks` | Task, TaskChecklistItem, TaskComment |
| `app.modules.shopping` | `/families/*/shopping` | ShoppingList, ShoppingItem |
| `app.modules.health.patients` | `/families/*/health/patients` | Patient |
| `app.modules.health.medical_records` | `/families/*/health/patients/*/records` | MedicalRecord |
| `app.modules.health.doctors` | `/families/*/health/doctors` | Doctor |
| `app.modules.health.medicines` | `/families/*/health/patients/*/medicines` | Medicine |
| `app.modules.health.appointments` | `/families/*/health/patients/*/appointments` | Appointment |

## Running it

```bash
cd service-flask
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt   # .venv/bin/pip on macOS/Linux
.venv/Scripts/python -m app.main                # .venv/bin/python -m app.main on macOS/Linux
```

Run it as a module (`-m app.main`), not as a script (`python app/main.py`) -
otherwise Python puts `app/` itself on `sys.path` instead of the project
root, and the `app.core`/`app.modules` imports fail.

Defaults to `0.0.0.0:8000` and creates `inovera.db` in this directory on
first run (dev convenience - production schema changes still belong in a
real migration tool, same as the FastAPI original noted for its own
`init_models()`). Configure via `.env` (see the one already in this
directory) - same variable names as `Service/.env`.

Because both backends default to port 8000, don't run them at the same
time on the same machine without changing one's port.
