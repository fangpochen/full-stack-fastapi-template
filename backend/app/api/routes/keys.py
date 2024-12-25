from typing import Any
import secrets
from fastapi import APIRouter, Depends, HTTPException, Body, Request
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select, func
from datetime import datetime, timedelta
import uuid
import logging
from sqlmodel import SQLModel, select, func
from sqlalchemy.orm import selectinload
from pydantic import BaseModel
from passlib.hash import scrypt
from typing import Dict, Tuple
import time

from app.api.deps import CurrentUser, SessionDep
from app.models import ApiKey, ApiKeysPublic, ApiKeyCreate, ApiKeyBase

router = APIRouter(prefix="/api-keys", tags=["api-keys"])

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# 存储 IP 访问记录的字典 {ip: (count, first_access_time)}
ip_access_records: Dict[str, Tuple[int, float]] = {}

# IP 限制的配置
IP_RATE_LIMIT = 3  # 最大尝试次数
IP_RATE_WINDOW = 3600  # 时间窗口（秒）

def check_ip_rate_limit(request: Request) -> bool:
    """检查 IP 访问频率限制"""
    client_ip = request.client.host
    current_time = time.time()
    
    # 清理过期的记录
    expired_ips = [
        ip for ip, (_, access_time) in ip_access_records.items()
        if current_time - access_time > IP_RATE_WINDOW
    ]
    for ip in expired_ips:
        del ip_access_records[ip]
    
    # 检查当前 IP 的访问记录
    if client_ip in ip_access_records:
        count, first_access = ip_access_records[client_ip]
        # 如果在时间窗口内
        if current_time - first_access < IP_RATE_WINDOW:
            if count >= IP_RATE_LIMIT:
                remaining_time = int(IP_RATE_WINDOW - (current_time - first_access))
                raise HTTPException(
                    status_code=429,
                    detail=f"Too many attempts. Try again in {remaining_time} seconds"
                )
            # 增加计数
            ip_access_records[client_ip] = (count + 1, first_access)
        else:
            # 超过时间窗口，重置计数
            ip_access_records[client_ip] = (1, current_time)
    else:
        # 新的 IP 访问
        ip_access_records[client_ip] = (1, current_time)
    
    return True

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
    api_key_in: dict = Body(...),
):
    """批量创建API密钥"""
    data = api_key_in.get('count', {})
    count = data.get('count', 1)
    item_id = api_key_in.get('item_id')
    
    api_keys = []
    for _ in range(count):
        # 生成原始密钥
        raw_key = secrets.token_urlsafe(32)
        # 使用 scrypt 加密
        hashed_key = scrypt.hash(raw_key)
        
        api_key = ApiKey(
            key=raw_key,  # 存储原始密钥，���为需要显示给用户
            hashed_key=hashed_key,  # 存储加密后的密钥
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

@router.post("/verify", status_code=200)
async def verify_api_key(
    request: Request,
    session: SessionDep,
    data: dict = Body(...),  # 接收包含 key 和 machine_info 的数据
):
    """验证 API 密钥（无需登录）"""
    try:
        # 检查 IP 限制
        check_ip_rate_limit(request)
        
        key = data.get('key')
        machine_info = data.get('machine_info', {})
        
        # 查找密钥
        api_key = session.exec(
            select(ApiKey).where(ApiKey.key == key)
        ).first()
        
        if not api_key or not api_key.is_active:
            return {"valid": False}
        
        # 如果已经绑定，检查设备信息是否匹配
        if api_key.is_bound:
            if api_key.machine_info != machine_info:
                logger.warning(f"Device mismatch for key {api_key.id}")
                return {"valid": False, "message": "Device not matched"}
        else:
            # 首次绑定，更新设备信息
            api_key.machine_info = machine_info
            api_key.is_bound = True
            
        # 更新最后验证时间
        api_key.last_verified_at = datetime.utcnow()
        session.commit()
        
        # 验证成功，重置该 IP 的计数
        client_ip = request.client.host
        if client_ip in ip_access_records:
            del ip_access_records[client_ip]
        
        return {"valid": True}
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error verifying API key: {e}")
        return {"valid": False}