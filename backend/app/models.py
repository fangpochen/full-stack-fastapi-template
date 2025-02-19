import uuid
from datetime import datetime
from typing import Dict, Optional, List
from pydantic import EmailStr
from sqlmodel import Field, Relationship, SQLModel
from sqlalchemy import JSON
from sqlalchemy import UniqueConstraint


# Shared properties
class UserBase(SQLModel):
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    is_active: bool = True
    is_superuser: bool = False
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on creation
class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=40)


class UserRegister(SQLModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=40)
    full_name: str | None = Field(default=None, max_length=255)
    invite_code: str


# Properties to receive via API on update, all are optional
class UserUpdate(UserBase):
    email: EmailStr | None = Field(default=None, max_length=255)  # type: ignore
    password: str | None = Field(default=None, min_length=8, max_length=40)


class UserUpdateMe(SQLModel):
    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)


class UpdatePassword(SQLModel):
    current_password: str = Field(min_length=8, max_length=40)
    new_password: str = Field(min_length=8, max_length=40)


# Database model, database table inferred from class name
class User(UserBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    hashed_password: str
    items: list["Item"] = Relationship(back_populates="owner", cascade_delete=True)
    apikey: list["ApiKey"] = Relationship(back_populates="user")
    project_permissions: list["UserProjectPermission"] = Relationship(back_populates="user")


# Properties to return via API, id is always required
class UserPublic(UserBase):
    id: uuid.UUID


class UsersPublic(SQLModel):
    data: list[UserPublic]
    count: int


# Shared properties
class ItemBase(SQLModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)


# Properties to receive on item creation
class ItemCreate(ItemBase):
    pass


# Properties to receive on item update
class ItemUpdate(ItemBase):
    title: str | None = Field(default=None, min_length=1, max_length=255)  # type: ignore


# Database model, database table inferred from class name
class Item(ItemBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    title: str = Field(max_length=255)
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    owner: User | None = Relationship(back_populates="items")
    keys: list["ApiKey"] = Relationship(back_populates="item")
    user_permissions: list["UserProjectPermission"] = Relationship(back_populates="item")


# Properties to return via API, id is always required
class ItemPublic(ItemBase):
    id: uuid.UUID
    owner_id: uuid.UUID


class ItemsPublic(SQLModel):
    data: list[ItemPublic]
    count: int


# Generic message
class Message(SQLModel):
    message: str


# JSON payload containing access token
class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


# Contents of JWT token
class TokenPayload(SQLModel):
    sub: str | None = None


class NewPassword(SQLModel):
    token: str
    new_password: str = Field(min_length=8, max_length=40)


# API Key base model
class ApiKeyBase(SQLModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    key: str = Field(unique=True, index=True)
    unique_id: str = Field(max_length=255)
    machine_info: Dict = Field(default={}, sa_type=JSON)
    version: str = Field(max_length=255)
    is_active: bool = Field(default=True)
    is_bound: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_verified_at: datetime | None = Field(default=None)
    expires_at: datetime | None = Field(default=None)


# Database model
class ApiKey(ApiKeyBase, table=True):
    key: str = Field(max_length=255)
    user_id: uuid.UUID = Field(foreign_key="user.id")
    user: "User" = Relationship(back_populates="apikey")
    item_id: uuid.UUID | None = Field(default=None, foreign_key="item.id", nullable=True)
    item: Item | None = Relationship(back_populates="keys")


# Properties to return via API
class ApiKeyPublic(ApiKeyBase):
    user_id: uuid.UUID
    item_id: uuid.UUID | None
    item: ItemPublic | None = None
    hashed_key: str | None = None  # 不返回给前端


# List response model
class ApiKeysPublic(SQLModel):
    data: list[ApiKeyPublic]
    count: int


# Create request model
class ApiKeyCreate(SQLModel):
    count: int = Field(gt=0, le=100)
    item_id: uuid.UUID | None 


# 邀请码模型
class InviteCode(SQLModel, table=True):
    """邀请码模型"""
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    code: str = Field(unique=True, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = Field(default=None)
    is_used: bool = Field(default=False)
    used_at: Optional[datetime] = Field(default=None)
    used_by: Optional[str] = Field(default=None)
    created_by: Optional[str] = Field(default=None)
    description: Optional[str] = Field(default=None) 


# 用户项目权限级别枚举
class UserProjectRole(str):
    ADMIN = "admin"  # 管理员权限
    WRITE = "write"  # 写入权限
    READ = "read"   # 只读权限


# 用户项目权限模型
class UserProjectPermission(SQLModel, table=True):
    """用户项目权限模型"""
    __tablename__ = "user_project_permissions"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="user.id")
    item_id: uuid.UUID = Field(foreign_key="item.id")
    role: str = Field(default="read")  # read, write, admin
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('user_id', 'item_id', name='uix_user_project'),
    )

    user: "User" = Relationship(back_populates="project_permissions")
    item: "Item" = Relationship(back_populates="user_permissions")


# API 响应模型
class UserProjectPermissionPublic(SQLModel):
    id: uuid.UUID
    user_id: uuid.UUID
    item_id: uuid.UUID
    role: str
    created_at: datetime
    updated_at: datetime | None
    user: UserPublic | None = None
    item: ItemPublic | None = None


class UserProjectPermissionsPublic(SQLModel):
    data: list[UserProjectPermissionPublic]
    count: int


# 创建权限请求模型
class UserProjectPermissionCreate(SQLModel):
    user_id: uuid.UUID
    item_id: uuid.UUID
    role: str = Field(default=UserProjectRole.READ)


# 更新权限请求模型
class UserProjectPermissionUpdate(SQLModel):
    role: str 