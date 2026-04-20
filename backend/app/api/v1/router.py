"""V1 路由聚合."""

from fastapi import APIRouter

from app.api.v1 import analyses, auth, chat, common, users

api_router = APIRouter()

api_router.include_router(common.router, tags=["通用"])
api_router.include_router(auth.router, prefix="/auth", tags=["认证"])
api_router.include_router(users.router, prefix="/users", tags=["用户"])
api_router.include_router(analyses.router, prefix="/analyses", tags=["分析"])
api_router.include_router(chat.router, prefix="/chat", tags=["AI 对话"])
