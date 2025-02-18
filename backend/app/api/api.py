from fastapi import APIRouter
from app.api.routes import auth, users, items, keys, ffmpeg

api_router = APIRouter()
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(items.router, prefix="/items", tags=["items"])
api_router.include_router(keys.router, prefix="/api-keys", tags=["api-keys"])
api_router.include_router(ffmpeg.router, prefix="/ffmpeg", tags=["ffmpeg"])