import uuid
from typing import Any, Optional
from datetime import datetime
from sqlalchemy import or_

from sqlmodel import Session, select

from app.core.security import get_password_hash, verify_password
from app.models import Item, ItemCreate, User, UserCreate, UserUpdate, InviteCode


def create_user(*, session: Session, user_create: UserCreate) -> User:
    db_obj = User.model_validate(
        user_create, update={"hashed_password": get_password_hash(user_create.password)}
    )
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def update_user(*, session: Session, db_user: User, user_in: UserUpdate) -> Any:
    user_data = user_in.model_dump(exclude_unset=True)
    extra_data = {}
    if "password" in user_data:
        password = user_data["password"]
        hashed_password = get_password_hash(password)
        extra_data["hashed_password"] = hashed_password
    db_user.sqlmodel_update(user_data, update=extra_data)
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user


def get_user_by_email(*, session: Session, email: str) -> User | None:
    statement = select(User).where(User.email == email)
    session_user = session.exec(statement).first()
    return session_user


def authenticate(*, session: Session, email: str, password: str) -> User | None:
    db_user = get_user_by_email(session=session, email=email)
    if not db_user:
        return None
    if not verify_password(password, db_user.hashed_password):
        return None
    return db_user


def create_item(*, session: Session, item_in: ItemCreate, owner_id: uuid.UUID) -> Item:
    db_item = Item.model_validate(item_in, update={"owner_id": owner_id})
    session.add(db_item)
    session.commit()
    session.refresh(db_item)
    return db_item


def get_invite_code_by_code(session: Session, code: str) -> Optional[InviteCode]:
    """根据邀请码获取记录"""
    return session.exec(
        select(InviteCode).where(InviteCode.code == code)
    ).first()


def mark_invite_code_as_used(
    session: Session, 
    invite: InviteCode, 
    user: User
) -> InviteCode:
    """标记邀请码为已使用"""
    invite.is_used = True
    invite.used_at = datetime.utcnow()
    invite.used_by = str(user.id)
    session.add(invite)
    session.commit()
    session.refresh(invite)
    return invite


def create_invite_codes(
    session: Session,
    count: int = 1,
    created_by: Optional[str] = None
) -> list[InviteCode]:
    """批量创建邀请码"""
    from secrets import token_urlsafe
    
    codes = []
    for _ in range(count):
        code = InviteCode(
            code=token_urlsafe(8),
            created_by=created_by
        )
        session.add(code)
        codes.append(code)
    
    session.commit()
    for code in codes:
        session.refresh(code)
    
    return codes
