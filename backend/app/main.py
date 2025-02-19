import sentry_sdk
from fastapi import FastAPI
from fastapi.routing import APIRoute
from starlette.middleware.cors import CORSMiddleware
import logging
from logging.handlers import RotatingFileHandler
import os
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.api.main import api_router
from app.core.config import settings
from app.tasks.cleanup import cleanup_expired_keys

# 创建日志目录
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        # 控制台输出
        logging.StreamHandler(),
        # 文件输出，使用 RotatingFileHandler 自动轮转日志文件
        RotatingFileHandler(
            os.path.join(LOG_DIR, 'app.log'),
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
    ]
)

# 获取根日志记录器
logger = logging.getLogger()

def custom_generate_unique_id(route: APIRoute) -> str:
    """为路由生成唯一ID"""
    if route.tags and len(route.tags) > 0:
        return f"{route.tags[0]}-{route.name}"
    return route.name  # 如果没有 tags，就只使用 name


if settings.SENTRY_DSN and settings.ENVIRONMENT != "local":
    sentry_sdk.init(dsn=str(settings.SENTRY_DSN), enable_tracing=True)

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    generate_unique_id_function=custom_generate_unique_id,
)

# Set all CORS enabled origins
if settings.all_cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.all_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(api_router, prefix=settings.API_V1_STR)

# 设置定时任务
scheduler = AsyncIOScheduler()

@app.on_event("startup")
async def startup_event():
    # 每天凌晨 2 点运行清理任务
    scheduler.add_job(
        cleanup_expired_keys,
        trigger=CronTrigger(hour=2, minute=0),
        id="cleanup_expired_keys",
        name="Cleanup expired API keys",
        replace_existing=True
    )
    scheduler.start()
    logger.info("Started scheduler for API key cleanup")

@app.on_event("shutdown")
async def shutdown_event():
    scheduler.shutdown()
    logger.info("Shut down scheduler")
