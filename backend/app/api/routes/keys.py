from typing import Any
import secrets
from fastapi import APIRouter, Depends, HTTPException, Body
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select, func
from datetime import datetime
import uuid
import logging
from sqlmodel import SQLModel, select, func
from sqlalchemy.orm import selectinload
from pydantic import BaseModel

from app.api.deps import CurrentUser, SessionDep
from app.models import ApiKey, ApiKeysPublic, ApiKeyCreate, ApiKeyBase

router = APIRouter(prefix="/api-keys", tags=["api-keys"])

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

@router.get("/", response_model=ApiKeysPublic)
def read_keys(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
) -> ApiKeysPublic:
    """
    检索密钥列表。
    """
    if current_user.is_superuser:
        count = session.exec(select(func.count(ApiKey.id))).one()
        keys = session.exec(select(ApiKey)
                            .options(selectinload(ApiKey.item))
                            .offset(skip).limit(limit)).all()
    else:
        count = session.exec(
            select(func.count(ApiKey.id)).where(ApiKey.user_id == current_user.id)
        ).one()
        keys = session.exec(
            select(ApiKey)
            .options(selectinload(ApiKey.item))
            .where(ApiKey.user_id == current_user.id)
            .offset(skip)
            .limit(limit)
        ).all()

    # 移除对 key_tuple 的处理，直接返回 keys
    return ApiKeysPublic(
        data=keys,
        count=count
    )

@router.post("/create", response_model=ApiKeysPublic)
async def create_api_keys(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    api_key_in: dict = Body(...),  # 直接接收字典
):
    """批量创建API密钥"""
    data=api_key_in.get('count', {})
    count = data.get('count', 1)
    item_id = api_key_in.get('item_id')
    
    api_keys = []
    for _ in range(count):
        api_key = ApiKey(
            key=secrets.token_urlsafe(32),
            unique_id=str(uuid.uuid4()),
            machine_info={},
            version="1.0",
            is_active=True,
            created_at=datetime.utcnow(),
            user_id=current_user.id,
            item_id=item_id
        )
        session.add(api_key)
        api_keys.append(api_key)
    
    session.commit()
    return ApiKeysPublic(data=api_keys, count=len(api_keys))

@router.delete("/batch")
def batch_delete_api_keys(
    session: SessionDep,
    current_user: CurrentUser,
    key_ids: list[str] = Body(...),
):
    """批量删除API密钥"""
    try:
        logger.debug(f"Received key_ids: {key_ids}")
        
        uuid_ids = [uuid.UUID(key_id) for key_id in key_ids]
        
        keys = session.exec(
            select(ApiKey)
            .where(ApiKey.id.in_(uuid_ids))
            .where(ApiKey.user_id == current_user.id)
        ).all()
        
        for key in keys:
            session.delete(key)
        session.commit()
        
        return {"status": "success", "count": len(keys)}
    except ValueError as e:
        logger.error(f"Invalid UUID format: {e}")
        raise HTTPException(status_code=422, detail="Invalid UUID format")
    except Exception as e:
        logger.error(f"Error in batch delete: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{key_id}")
def delete_api_key(
    key_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
):
    """删除API密钥"""
    api_key = session.get(ApiKey, key_id)
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")
    
    session.delete(api_key)
    session.commit()
    return {"status": "success"}

@router.put("/{key_id}/toggle")
def toggle_api_key(
    key_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
) -> ApiKey:
    """切换API密钥状态"""
    api_key = session.get(ApiKey, key_id)
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")
    
    api_key.is_active = not api_key.is_active
    session.commit()
    session.refresh(api_key)
    return api_key