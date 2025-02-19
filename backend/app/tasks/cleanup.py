"""定时任务：清理过期的 API 密钥"""

import logging
from datetime import datetime
from sqlmodel import select, Session
from app.models import ApiKey
from app.core.db import engine

logger = logging.getLogger(__name__)

def cleanup_expired_keys():
    """清理过期的 API 密钥"""
    try:
        with Session(engine) as session:
            # 查找所有过期且仍然激活的密钥
            query = select(ApiKey).where(
                ApiKey.expires_at < datetime.utcnow(),
                ApiKey.is_active == True
            )
            expired_keys = session.exec(query).all()
            
            # 停用过期的密钥
            for key in expired_keys:
                key.is_active = False
                logger.info(f"Deactivating expired API key: {key.id}")
            
            session.commit()
            
            logger.info(f"Successfully deactivated {len(expired_keys)} expired API keys")
            
    except Exception as e:
        logger.error(f"Error cleaning up expired API keys: {e}") 