import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.doctor import Doctor


class DoctorError(Exception):
    """Raised for any doctor-domain failure the router should turn into an HTTP error."""


def create_doctor(
    db: Session,
    family_id: uuid.UUID,
    user_id: uuid.UUID,
    name: str,
    specialty: str | None,
    phone: str | None,
    notes: str | None,
) -> Doctor:
    doctor = Doctor(family_id=family_id, name=name, specialty=specialty, phone=phone, notes=notes, created_by_user_id=user_id)
    db.add(doctor)
    db.commit()
    db.refresh(doctor)
    return doctor


def list_doctors(db: Session, family_id: uuid.UUID) -> list[Doctor]:
    result = db.scalars(select(Doctor).where(Doctor.family_id == family_id).order_by(Doctor.name))
    return list(result)


def _get_doctor_row(db: Session, family_id: uuid.UUID, doctor_id: uuid.UUID) -> Doctor:
    doctor = db.get(Doctor, doctor_id)
    if not doctor or doctor.family_id != family_id:
        raise DoctorError("Doctor not found")
    return doctor


def update_doctor(
    db: Session,
    family_id: uuid.UUID,
    doctor_id: uuid.UUID,
    *,
    name: str | None = None,
    specialty: str | None = None,
    clear_specialty: bool = False,
    phone: str | None = None,
    clear_phone: bool = False,
    notes: str | None = None,
    clear_notes: bool = False,
) -> Doctor:
    doctor = _get_doctor_row(db, family_id, doctor_id)
    if name is not None:
        doctor.name = name
    if clear_specialty:
        doctor.specialty = None
    elif specialty is not None:
        doctor.specialty = specialty
    if clear_phone:
        doctor.phone = None
    elif phone is not None:
        doctor.phone = phone
    if clear_notes:
        doctor.notes = None
    elif notes is not None:
        doctor.notes = notes
    db.commit()
    db.refresh(doctor)
    return doctor


def delete_doctor(db: Session, family_id: uuid.UUID, doctor_id: uuid.UUID) -> None:
    doctor = _get_doctor_row(db, family_id, doctor_id)
    # Un-link any appointments pointing at this doctor first - doctor_id is a
    # real FK, so SQLite's foreign_keys=ON would reject the delete otherwise.
    appointments = db.scalars(select(Appointment).where(Appointment.doctor_id == doctor_id))
    for appointment in appointments:
        appointment.doctor_id = None
    db.flush()
    db.delete(doctor)
    db.commit()
