from typing import Any
import secrets
from fastapi import APIRouter, Depends, HTTPException, Body, Request, Query
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select, func
from datetime import datetime, timedelta
import uuid
import logging
from sqlmodel import SQLModel, select, func
from sqlalchemy.orm import selectinload
from pydantic import BaseModel
from passlib.hash import scrypt
from typing import Dict, Tuple, Optional
import time
from math import ceil

from app.api.deps import CurrentUser, SessionDep
from app.models import ApiKey, ApiKeysPublic, ApiKeyCreate, ApiKeyBase, User

router = APIRouter(prefix="/api-keys", tags=["api-keys"])

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# 存储 IP 访问记录的字典 {ip: (count, first_access_time)}
ip_access_records: Dict[str, Tuple[int, float]] = {}

# IP 限制的配置
IP_RATE_LIMIT = 10  # 最大尝试次数
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
            key=raw_key,  # 存储原始密钥，为需要显示给用户
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
    data: dict = Body(...),
):
    """验证 API 密钥（无需登录）"""
    try:
        # 检查 IP 限制
        check_ip_rate_limit(request)
        
        key = data.get('key')
        machine_info = data.get('machine_info', {})
        
        # 添加 IP 信息
        machine_info.update({
            'ip_address': request.client.host,
            'last_access_time': datetime.utcnow().isoformat()
        })
        
        # 如果有 X-Forwarded-For 头，也记录它
        forwarded_for = request.headers.get('X-Forwarded-For')
        if forwarded_for:
            machine_info['x_forwarded_for'] = forwarded_for
        
        # 查找密钥
        api_key = session.exec(
            select(ApiKey).where(ApiKey.key == key)
        ).first()
        
        if not api_key or not api_key.is_active:
            return {"valid": False}
        # 如果 user_name 是 admin，检查密钥是否由管理员创建
        if machine_info.get('user_name') == 'admin':
            # 获取密钥创建者信息
            key_creator = session.get(User, api_key.user_id)
            if not key_creator or not key_creator.is_superuser:
                logger.warning(f"Non-admin key {api_key.id} attempted to be used with admin privileges")
                return {"valid": False, "message": "Invalid admin key"}
        # 如果已经绑定，检查设备信息是否匹配
        if api_key.is_bound:
            stored_machine_info = api_key.machine_info.copy()
            # 更新 IP 相关信息但保留其他设备信息
            stored_machine_info.update({
                'ip_address': machine_info['ip_address'],
                'last_access_time': machine_info['last_access_time']
            })
            if forwarded_for:
                stored_machine_info['x_forwarded_for'] = machine_info['x_forwarded_for']
            
            api_key.machine_info = stored_machine_info
            
            
            
            device_mismatch = (
                stored_machine_info.get('hostname') != machine_info.get('hostname') or
                stored_machine_info.get('mac') != machine_info.get('mac') or
                stored_machine_info.get('device_id') != machine_info.get('device_id') or
                # 添加 item 和 user_name 的匹配检查，如果存在这些字段则进行比较
                (stored_machine_info.get('item') and machine_info.get('item') and 
                 stored_machine_info.get('item') != machine_info.get('item')) or
                (stored_machine_info.get('user_name') and machine_info.get('user_name') and 
                 stored_machine_info.get('user_name') != machine_info.get('user_name'))
            )
            
            if device_mismatch:
                logger.warning(f"Device mismatch for key {api_key.id}")
                logger.debug(f"Stored info: {stored_machine_info}")
                logger.debug(f"Received info: {machine_info}")
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

@router.get("")
async def list_api_keys(
    session: SessionDep,
    current_user: CurrentUser,
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=10, ge=1, le=100, description="每页数量"),
    search: Optional[str] = Query(None, description="搜索关键字"),
    is_active: Optional[bool] = Query(None, description="密钥状态"),
    item_id: Optional[str] = Query(None, description="项目ID"),
    user_id: Optional[str] = Query(None, description="用户ID，仅管理员可用")
):
    """获取 API 密钥列表（分页）"""
    if current_user.is_superuser:
        # 管理员可以查看所有密钥
        query = select(ApiKey).options(selectinload(ApiKey.item))
        if user_id:
            query = query.where(ApiKey.user_id == user_id)
    else:
        # 普通用户只能查看自己的密钥
        query = select(ApiKey).where(ApiKey.user_id == current_user.id)
    
    # 其他过滤条件...
    if search:
        query = query.where(ApiKey.key.contains(search))
    if is_active is not None:
        query = query.where(ApiKey.is_active == is_active)
    if item_id:
        query = query.where(ApiKey.item_id == item_id)
    
    # 计算总数
    total_count = session.exec(
        select(func.count()).select_from(query.subquery())
    ).one()
    
    # 添加排序和分页
    query = (query
        .order_by(ApiKey.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    
    # 执行查询
    keys = session.exec(query).all()
    
    # 计算总页数
    total_pages = ceil(total_count / page_size)
    
    return {
        "data": keys,
        "pagination": {
            "current_page": page,
            "page_size": page_size,
            "total": total_count,
            "total_pages": total_pages
        }
    }