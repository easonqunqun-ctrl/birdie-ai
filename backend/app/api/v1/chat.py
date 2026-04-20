"""AI 对话接口（对齐 docs/02-API接口设计文档.md §四 /chat）.

M3-T2 增量：
- POST /v1/chat/sessions/{id}/messages 默认走 **SSE**（`text/event-stream`）
- `Accept: application/json` 或 `?stream=false` 时降级到 T1 的非流式 JSON
- 速率限制：每用户每分钟 20 次（40009）

SSE 事件格式
-------------
每个事件形如：

    event: message_start
    data: {"user_message_id": "msg_xxx", ...}

    event: content_delta
    data: {"delta": "好的"}

    event: error
    data: {"code": 50106, "message": "AI 教练暂时开小差了"}

前端 Mini Program 需用 `wx.request({ enableChunked: true })` + `onChunkReceived`
自行按 `\\n\\n` 分帧解析（见 client T4）。
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.constants.chat_quick_questions import QUICK_QUESTIONS
from app.core.database import get_db
from app.core.rate_limit import check_chat_send_rate
from app.core.redis import get_redis
from app.models.user import User
from app.schemas.base import APIResponse, PageData, ok
from app.schemas.chat import (
    ChatMessageItem,
    ChatSessionListItem,
    CreateSessionRequest,
    CreateSessionResponse,
    QuickQuestionItem,
    QuickQuestionsResponse,
    SendMessageRequest,
)
from app.services import chat_service

router = APIRouter()


# ==================== 4.6 快捷问题 ====================
@router.get(
    "/quick-questions",
    summary="获取快捷问题列表",
    response_model=APIResponse[QuickQuestionsResponse],
)
async def get_quick_questions():
    items = [QuickQuestionItem(**q) for q in QUICK_QUESTIONS]
    return ok(QuickQuestionsResponse(questions=items))


# ==================== 4.1 创建/获取会话 ====================
@router.post(
    "/sessions",
    summary="创建或获取活跃会话",
    response_model=APIResponse[CreateSessionResponse],
)
async def create_session(
    payload: CreateSessionRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await chat_service.create_or_get_session(
        user=user, payload=payload, db=db
    )
    await db.commit()
    return ok(result)


# ==================== 4.4 会话列表 ====================
@router.get(
    "/sessions",
    summary="获取会话列表",
    response_model=APIResponse[PageData[ChatSessionListItem]],
)
async def list_sessions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await chat_service.list_sessions(
        user=user, page=page, page_size=page_size, db=db
    )
    return ok(result)


# ==================== 4.3 历史消息 ====================
@router.get(
    "/sessions/{session_id}/messages",
    summary="获取会话历史消息",
    response_model=APIResponse[PageData[ChatMessageItem]],
)
async def get_messages(
    session_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await chat_service.get_session_messages(
        user=user, session_id=session_id, page=page, page_size=page_size, db=db
    )
    return ok(result)


# ==================== 4.2 发送消息（默认 SSE，可降级 JSON） ====================
def _wants_sse(request: Request, stream_query: bool | None) -> bool:
    """是否走 SSE 路径。

    优先级：
    - `?stream=true` → SSE
    - `?stream=false` → JSON
    - `Accept: text/event-stream` → SSE
    - 其它（包括 */*）→ JSON（T1/T3 默认、curl 默认都走这条）

    为什么**默认 JSON** 而非 SSE：
    - REST 客户端（包括 httpx/curl/Python requests）默认 `Accept: */*`，
      一旦默认返回 SSE 就没法 `.json()` 解析了，踩坑率太高；
    - 前端（小程序 T4）开流式时会显式加 `Accept: text/event-stream`，成本很低；
    - 联调时用 `?stream=true` 或 `-H "Accept: text/event-stream"` 都能触发 SSE。
    """
    if stream_query is True:
        return True
    if stream_query is False:
        return False
    accept = (request.headers.get("accept") or "").lower()
    return "text/event-stream" in accept


async def _sse_event_stream(
    gen: AsyncIterator[dict], db: AsyncSession
) -> AsyncIterator[bytes]:
    """把业务事件字典流转成 SSE 帧字节流，并在末尾 commit 数据库。

    关键点：
    - 每个事件用 `event: <type>\\ndata: <json>\\n\\n` 格式
    - **一定在所有 yield 结束后 commit**：生成器期间 service 层多次 flush 但不会 commit，
      因为 FastAPI `get_db` 的生命周期里 commit/rollback 都交给我们显式管理。
    - 生成器内部如果抛异常（不是 LLM error chunk，而是真 Python 异常），我们 rollback；
      否则 commit。
    """
    try:
        async for event in gen:
            event_type = event.get("type", "message")
            payload = {k: v for k, v in event.items() if k != "type"}
            frame = (
                f"event: {event_type}\n"
                f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            )
            yield frame.encode("utf-8")
        await db.commit()
    except Exception:
        await db.rollback()
        raise


@router.post(
    "/sessions/{session_id}/messages",
    summary="发送消息（默认 SSE 流式；Accept=application/json 降级）",
)
async def send_message(
    session_id: str,
    payload: SendMessageRequest,
    request: Request,
    stream: bool | None = Query(default=None, description="false 强制 JSON；默认 SSE"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    # 速率限制：每分钟 20 次；超限直接抛 40009（在 service 前置，节省 LLM 开销）
    await check_chat_send_rate(redis, user.id)

    if not _wants_sse(request, stream):
        result = await chat_service.send_message_sync(
            user=user, session_id=session_id, content=payload.content, db=db
        )
        await db.commit()
        return ok(result, message="发送成功")

    # SSE 流式：**先**做权限/配额/落 user_msg（任何 4xx 在开流前就抛出）
    session, user_msg, quota, llm_messages = await chat_service.prepare_turn(
        db=db, user=user, session_id=session_id, content=payload.content
    )
    gen = chat_service.stream_message(
        session=session,
        user_msg=user_msg,
        quota=quota,
        llm_messages=llm_messages,
        db=db,
    )
    return StreamingResponse(
        _sse_event_stream(gen, db),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 对 nginx 明确关闭缓冲
        },
    )


# ==================== 4.7 删除会话 ====================
@router.delete(
    "/sessions/{session_id}",
    summary="删除会话",
    response_model=APIResponse[None],
)
async def delete_session(
    session_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await chat_service.delete_session(user=user, session_id=session_id, db=db)
    await db.commit()
    return ok(None, message="对话已清空")


