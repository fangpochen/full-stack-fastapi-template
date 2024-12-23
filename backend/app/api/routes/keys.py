from typing import Any
import secrets
from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select, func
from datetime import datetime
import uuid
import logging

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
        keys = session.exec(select(ApiKey).offset(skip).limit(limit)).all()
    else:
        count = session.exec(
            select(func.count(ApiKey.id)).where(ApiKey.user_id == current_user.id)
        ).one()
        keys = session.exec(
            select(ApiKey)
            .where(ApiKey.user_id == current_user.id)
            .offset(skip)
            .limit(limit)
        ).all()

    # 手动序列化每个 ApiKey 对象
    serialized_keys = []
    for key_tuple in keys:
        key = key_tuple[0]  # 获取元组中的 ApiKey 对象
        serialized_keys.append(key)

    return ApiKeysPublic(
        data=serialized_keys,
        count=count[0]
    )

@router.post("/create", response_model=ApiKeysPublic)
async def create_api_keys(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    api_key_in: ApiKeyCreate,
):
    """批量创建API密钥"""
    api_keys = []
    for _ in range(api_key_in.count):
        api_key = ApiKey(
            key=secrets.token_urlsafe(32),
            unique_id=str(uuid.uuid4()),
            machine_info={},
            version="1.0",
            is_active=True,
            created_at=datetime.utcnow(),
            user_id=current_user.id
        )
        session.add(api_key)
        api_keys.append(api_key)
    
    session.commit()
    return ApiKeysPublic(data=api_keys, count=len(api_keys))

@router.delete("/{key_id}", status_code=204)
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