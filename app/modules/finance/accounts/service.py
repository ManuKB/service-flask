import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account import Account
from app.modules.finance.enums import AccountType


def create_account(
    db: Session, family_id: uuid.UUID, user_id: uuid.UUID, name: str, type_: AccountType
) -> Account:
    account = Account(family_id=family_id, name=name, type=type_, created_by_user_id=user_id)
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def list_accounts(db: Session, family_id: uuid.UUID) -> list[Account]:
    result = db.scalars(select(Account).where(Account.family_id == family_id).order_by(Account.created_at))
    return list(result)
