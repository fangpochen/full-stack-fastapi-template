from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select, Session
from sqlalchemy.orm import selectinload
from sqlalchemy import func
from datetime import datetime
import uuid
import logging
from typing import Optional

from app.api.deps import CurrentUser, SessionDep
from app.models import (
    UserProjectPermission, UserProjectPermissionsPublic, UserProjectPermissionPublic,
    UserProjectPermissionCreate, UserProjectPermissionUpdate, UserProjectRole,
    User, Item, UserPublic, ItemPublic
)

router = APIRouter(prefix="/permissions", tags=["permissions"])
logger = logging.getLogger(__name__)

def check_project_permission(session: Session, user_id: uuid.UUID, item_id: uuid.UUID, required_role: str) -> bool:
    """检查用户是否有项目的指定权限"""
    # 获取用户
    user = session.get(User, user_id)
    if not user:
        return False
    
    # 超级管理员拥有所有权限
    if user.is_superuser:
        return True
    
    # 检查项目所有者
    item = session.get(Item, item_id)
    if item and item.owner_id == user_id:
        return True
    
    # 检查用户项目权限
    permission = session.exec(
        select(UserProjectPermission)
        .where(
            UserProjectPermission.user_id == user_id,
            UserProjectPermission.item_id == item_id
        )
    ).first()
    
    if not permission:
        return False
    
    # 权限等级检查
    role_levels = {
        UserProjectRole.READ: 1,
        UserProjectRole.WRITE: 2,
        UserProjectRole.ADMIN: 3
    }
    
    return role_levels.get(permission.role, 0) >= role_levels.get(required_role, 0)

@router.get("", response_model=UserProjectPermissionsPublic)
async def list_permissions(
    session: SessionDep,
    current_user: CurrentUser,
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=10, ge=1, le=100, description="每页数量"),
    user_id: Optional[uuid.UUID] = Query(None, description="用户ID"),
    item_id: Optional[uuid.UUID] = Query(None, description="项目ID")
):
    """获取权限列表"""
    if not current_user.is_superuser and (user_id != current_user.id):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    query = select(UserProjectPermission).options(
        selectinload(UserProjectPermission.user),
        selectinload(UserProjectPermission.item)
    )
    
    if user_id:
        query = query.where(UserProjectPermission.user_id == user_id)
    if item_id:
        query = query.where(UserProjectPermission.item_id == item_id)
    
    total = session.exec(select(func.count()).select_from(query.subquery())).one()
    
    permissions = session.exec(
        query.offset((page - 1) * page_size).limit(page_size)
    ).all()
    
    # 转换为公开模型
    result = []
    for perm in permissions:
        user_public = UserPublic(
            id=perm.user.id,
            email=perm.user.email,
            is_active=perm.user.is_active,
            is_superuser=perm.user.is_superuser,
            full_name=perm.user.full_name
        ) if perm.user else None
        
        item_public = ItemPublic(
            id=perm.item.id,
            title=perm.item.title,
            description=perm.item.description,
            owner_id=perm.item.owner_id
        ) if perm.item else None
        
        perm_public = UserProjectPermissionPublic(
            id=perm.id,
            user_id=perm.user_id,
            item_id=perm.item_id,
            role=perm.role,
            created_at=perm.created_at,
            updated_at=perm.updated_at,
            user=user_public,
            item=item_public
        )
        result.append(perm_public)
    
    return UserProjectPermissionsPublic(data=result, count=total)

@router.post("", response_model=UserProjectPermissionPublic)
async def create_permission(
    session: SessionDep,
    current_user: CurrentUser,
    permission_in: UserProjectPermissionCreate
):
    """创建项目权限"""
    # 检查权限
    if not current_user.is_superuser:
        item = session.get(Item, permission_in.item_id)
        if not item or item.owner_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not enough permissions")
    
    # 检查用户和项目是否存在
    user = session.get(User, permission_in.user_id)
    item = session.get(Item, permission_in.item_id)
    if not user or not item:
        raise HTTPException(status_code=404, detail="User or Item not found")
    
    # 检查是否已存在权限
    existing = session.exec(
        select(UserProjectPermission).where(
            UserProjectPermission.user_id == permission_in.user_id,
            UserProjectPermission.item_id == permission_in.item_id
        )
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Permission already exists")
    
    # 创建权限
    permission = UserProjectPermission(
        user_id=permission_in.user_id,
        item_id=permission_in.item_id,
        role=permission_in.role
    )
    session.add(permission)
    session.commit()
    session.refresh(permission)
    
    return UserProjectPermissionPublic(
        id=permission.id,
        user_id=permission.user_id,
        item_id=permission.item_id,
        role=permission.role,
        created_at=permission.created_at,
        updated_at=permission.updated_at
    )

@router.put("/{permission_id}", response_model=UserProjectPermissionPublic)
async def update_permission(
    permission_id: uuid.UUID,
    permission_in: UserProjectPermissionUpdate,
    session: SessionDep,
    current_user: CurrentUser
):
    """更新项目权限"""
    permission = session.get(UserProjectPermission, permission_id)
    if not permission:
        raise HTTPException(status_code=404, detail="Permission not found")
    
    # 检查权限
    if not current_user.is_superuser:
        item = session.get(Item, permission.item_id)
        if not item or item.owner_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not enough permissions")
    
    # 更新权限
    permission.role = permission_in.role
    permission.updated_at = datetime.utcnow()
    session.commit()
    session.refresh(permission)
    
    return UserProjectPermissionPublic(
        id=permission.id,
        user_id=permission.user_id,
        item_id=permission.item_id,
        role=permission.role,
        created_at=permission.created_at,
        updated_at=permission.updated_at
    )

@router.delete("/{permission_id}")
async def delete_permission(
    permission_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser
):
    """删除项目权限"""
    permission = session.get(UserProjectPermission, permission_id)
    if not permission:
        raise HTTPException(status_code=404, detail="Permission not found")
    
    # 检查权限
    if not current_user.is_superuser:
        item = session.get(Item, permission.item_id)
        if not item or item.owner_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not enough permissions")
    
    session.delete(permission)
    session.commit()
    
    return {"status": "success"} 