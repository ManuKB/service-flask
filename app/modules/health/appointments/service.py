import uuid
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.doctor import Doctor
from app.models.family_membership import FamilyMembership
from app.models.patient import Patient
from app.modules.audit.service import record_event
from app.modules.calendar.calendars.service import ensure_default_calendar
from app.modules.calendar.enums import ReminderLeadTime
from app.modules.calendar.events.service import create_event
from app.modules.calendar.reminders.service import create_reminder
from app.modules.health.patients.service import authorize_patient

APPOINTMENT_DURATION = timedelta(minutes=30)
DEFAULT_REMINDER_LEAD_TIME = ReminderLeadTime.ONE_DAY


class AppointmentError(Exception):
    """Raised for any appointment-domain failure the router should turn into an HTTP error."""


def _validate_doctor(db: Session, family_id: uuid.UUID, doctor_id: uuid.UUID) -> None:
    doctor = db.get(Doctor, doctor_id)
    if not doctor or doctor.family_id != family_id:
        raise AppointmentError("Doctor not found")


def create_appointment(
    db: Session,
    family_id: uuid.UUID,
    user_id: uuid.UUID,
    patient_id: uuid.UUID,
    membership: FamilyMembership,
    doctor_id: uuid.UUID | None,
    scheduled_at: datetime,
    notes: str | None,
    create_calendar_event: bool,
    reminder_enabled: bool,
) -> Appointment:
    patient: Patient = authorize_patient(db, family_id, patient_id, membership)
    if doctor_id is not None:
        _validate_doctor(db, family_id, doctor_id)

    calendar_event_id = None
    if create_calendar_event:
        # S5-05: "Appointment can create a calendar event" - reuses
        # calendar-service's own create_event rather than inventing a
        # parallel scheduling concept, same cross-module call pattern as
        # invitation-service -> family-service.
        calendar = ensure_default_calendar(db, family_id, user_id)
        title = f"{patient.name}'s appointment"
        event = create_event(
            db,
            family_id,
            user_id,
            calendar.id,
            title,
            notes,
            None,
            scheduled_at,
            scheduled_at + APPOINTMENT_DURATION,
            [],
            None,
            1,
            None,
            None,
        )
        calendar_event_id = event.id

    appointment = Appointment(
        patient_id=patient_id,
        doctor_id=doctor_id,
        scheduled_at=scheduled_at,
        notes=notes,
        calendar_event_id=calendar_event_id,
        reminder_enabled=reminder_enabled,
        created_by_user_id=user_id,
    )
    db.add(appointment)
    db.commit()
    db.refresh(appointment)

    if reminder_enabled and calendar_event_id is not None:
        # Reuses the existing calendar-reminder + scheduler + notification
        # infrastructure (S3-03) rather than a fourth notification variant -
        # the "reminder hook" is just enabling a Reminder on the appointment's event.
        create_reminder(db, family_id, user_id, calendar_event_id, DEFAULT_REMINDER_LEAD_TIME)

    record_event(
        db,
        family_id=family_id,
        actor_user_id=user_id,
        action="appointment.created",
        entity_type="Appointment",
        entity_id=appointment.id,
        new_value={"patient_id": str(patient_id), "scheduled_at": scheduled_at.isoformat()},
        source_service="health",
    )
    return appointment


def _get_appointment_row(db: Session, patient_id: uuid.UUID, appointment_id: uuid.UUID) -> Appointment:
    appointment = db.get(Appointment, appointment_id)
    if not appointment or appointment.patient_id != patient_id:
        raise AppointmentError("Appointment not found")
    return appointment


def get_appointment(
    db: Session,
    family_id: uuid.UUID,
    user_id: uuid.UUID,
    patient_id: uuid.UUID,
    appointment_id: uuid.UUID,
    membership: FamilyMembership,
) -> Appointment:
    authorize_patient(db, family_id, patient_id, membership)
    appointment = _get_appointment_row(db, patient_id, appointment_id)

    record_event(
        db,
        family_id=family_id,
        actor_user_id=user_id,
        action="appointment.viewed",
        entity_type="Appointment",
        entity_id=appointment.id,
        source_service="health",
    )
    return appointment


def list_appointments(
    db: Session, family_id: uuid.UUID, patient_id: uuid.UUID, membership: FamilyMembership
) -> list[Appointment]:
    authorize_patient(db, family_id, patient_id, membership)
    result = db.scalars(
        select(Appointment).where(Appointment.patient_id == patient_id).order_by(Appointment.scheduled_at)
    )
    return list(result)


def update_appointment(
    db: Session,
    family_id: uuid.UUID,
    user_id: uuid.UUID,
    patient_id: uuid.UUID,
    appointment_id: uuid.UUID,
    membership: FamilyMembership,
    *,
    doctor_id: uuid.UUID | None = None,
    clear_doctor: bool = False,
    scheduled_at: datetime | None = None,
    notes: str | None = None,
    clear_notes: bool = False,
    reminder_enabled: bool | None = None,
) -> Appointment:
    authorize_patient(db, family_id, patient_id, membership)
    appointment = _get_appointment_row(db, patient_id, appointment_id)

    if clear_doctor:
        appointment.doctor_id = None
    elif doctor_id is not None:
        _validate_doctor(db, family_id, doctor_id)
        appointment.doctor_id = doctor_id
    if scheduled_at is not None:
        appointment.scheduled_at = scheduled_at
    if clear_notes:
        appointment.notes = None
    elif notes is not None:
        appointment.notes = notes
    if reminder_enabled is not None:
        appointment.reminder_enabled = reminder_enabled
        if reminder_enabled and appointment.calendar_event_id is not None:
            create_reminder(db, family_id, user_id, appointment.calendar_event_id, DEFAULT_REMINDER_LEAD_TIME)

    db.commit()
    db.refresh(appointment)

    record_event(
        db,
        family_id=family_id,
        actor_user_id=user_id,
        action="appointment.updated",
        entity_type="Appointment",
        entity_id=appointment.id,
        source_service="health",
    )
    return appointment


def delete_appointment(
    db: Session, family_id: uuid.UUID, patient_id: uuid.UUID, appointment_id: uuid.UUID, membership: FamilyMembership
) -> None:
    authorize_patient(db, family_id, patient_id, membership)
    appointment = _get_appointment_row(db, patient_id, appointment_id)
    db.delete(appointment)
    db.commit()
