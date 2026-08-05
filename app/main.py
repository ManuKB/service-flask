from flask import Flask, g, jsonify
from flask_cors import CORS

from app.core.config import get_settings
from app.core.database import SessionLocal, init_models
from app.core.exceptions import register_error_handlers
from app.core.scheduler import start_reminder_scheduler

_scheduler_stop_event = None


def create_app() -> Flask:
    settings = get_settings()
    app = Flask(settings.service_name)
    CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

    register_error_handlers(app)

    @app.before_request
    def _open_db_session() -> None:
        g.db = SessionLocal()

    @app.teardown_appcontext
    def _close_db_session(exception: BaseException | None = None) -> None:
        db = g.pop("db", None)
        if db is not None:
            if exception is not None:
                db.rollback()
            db.close()

    @app.get("/health")
    def health():
        return jsonify({"status": "ok", "service": settings.service_name})

    from app.modules.audit.router import bp as audit_bp
    from app.modules.auth.router import bp as auth_bp
    from app.modules.calendar.agenda.router import bp as calendar_agenda_bp
    from app.modules.calendar.calendars.router import bp as calendar_calendars_bp
    from app.modules.calendar.events.router import bp as calendar_events_bp
    from app.modules.calendar.reminders.router import bp as calendar_reminders_bp
    from app.modules.families.router import bp as families_bp
    from app.modules.finance.accounts.router import bp as finance_accounts_bp
    from app.modules.finance.bills.router import bp as finance_bills_bp
    from app.modules.finance.budgets.router import bp as finance_budgets_bp
    from app.modules.finance.categories.router import bp as finance_categories_bp
    from app.modules.finance.overview.router import bp as finance_overview_bp
    from app.modules.finance.transactions.router import bp as finance_transactions_bp
    from app.modules.health.appointments.router import bp as health_appointments_bp
    from app.modules.health.doctors.router import bp as health_doctors_bp
    from app.modules.health.medical_records.router import bp as health_medical_records_bp
    from app.modules.health.medicines.router import bp as health_medicines_bp
    from app.modules.health.patients.router import bp as health_patients_bp
    from app.modules.invitations.router import bp as invitations_bp
    from app.modules.notifications.push.router import bp as push_bp
    from app.modules.notifications.router import bp as notifications_bp
    from app.modules.shopping.router import bp as shopping_bp
    from app.modules.tasks.router import bp as tasks_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(families_bp)
    app.register_blueprint(invitations_bp)
    app.register_blueprint(audit_bp)
    app.register_blueprint(finance_accounts_bp)
    app.register_blueprint(finance_categories_bp)
    app.register_blueprint(finance_transactions_bp)
    app.register_blueprint(finance_budgets_bp)
    app.register_blueprint(finance_bills_bp)
    app.register_blueprint(finance_overview_bp)
    app.register_blueprint(calendar_calendars_bp)
    app.register_blueprint(calendar_events_bp)
    app.register_blueprint(calendar_agenda_bp)
    app.register_blueprint(calendar_reminders_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(push_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(shopping_bp)
    app.register_blueprint(health_patients_bp)
    app.register_blueprint(health_medical_records_bp)
    app.register_blueprint(health_doctors_bp)
    app.register_blueprint(health_medicines_bp)
    app.register_blueprint(health_appointments_bp)

    # Every model module must be imported (registering its class on
    # Base.metadata) before create_all() runs - the blueprint imports above
    # transitively import every service.py, which imports every model, so
    # this has to happen after them, not before.
    init_models()

    global _scheduler_stop_event
    _scheduler_stop_event = start_reminder_scheduler()

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True, use_reloader=False)
