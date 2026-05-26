"""AI 对话业务逻辑：会话管理 + LLM 回复（同步 JSON / SSE 流）.

范围要点
--------
- 会话：创建/复用活跃会话（24h 内）、列表、历史、删除；报告页带 `context_analysis_id`
  时总是新建会话。
- 回复：`get_llm_client()` + OpenAI 兼容流式接口；`LLM_MOCK_MODE` / 占位密钥可走 Fake；
  文本可走微信内容安全（配置开启时）。
- 配额：发送前预检与扣减。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.core.security import new_id
from app.integrations.llm import AbstractLLMClient, get_llm_client
from app.integrations.wechat_security import check_text as wechat_check_text
from app.models.analysis import SwingAnalysis
from app.models.chat import ChatMessage, ChatSession
from app.models.user import User
from app.schemas.base import PageData, page_data
from app.schemas.chat import (
    ChatMessageItem,
    ChatSessionListItem,
    CreateSessionRequest,
    CreateSessionResponse,
    MessageAttachment,
    SendMessageResponse,
)
from app.services import quota_service, user_profile_v2_service
from app.services.chat_prompt import (
    SYSTEM_PROMPT_VERSION,
    build_system_prompt,
    load_recent_analyses,
)
from app.services.chat_topic_boundary import classify_user_message, topic_boundary_refusal_for

# ==================== 常量 ====================
ACTIVE_SESSION_HOURS = 24
WELCOME_MESSAGE = (
    "你好！我是领翼golf 的 AI 高尔夫教练。"
    "随时可以问我挥杆技术、练习方法或高尔夫知识方面的问题。"
)
# 最长的消息预览字段（docs/03 §3.5 last_message_preview VARCHAR(200)，这里保守切 100）
PREVIEW_MAX_LEN = 100


@dataclass(frozen=True)
class PreparedTurn:
    """``prepare_turn`` 返回值：SSE 开流前完成校验 + 落库。"""

    session: ChatSession
    user_msg: ChatMessage
    quota: Any
    llm_messages: list[dict[str, str]]
    boundary_assistant: ChatMessage | None = None


# ==================== 内部辅助 ====================
def _to_item(m: ChatMessage) -> ChatMessageItem:
    return ChatMessageItem(
        id=m.id,
        role=m.role,  # type: ignore[arg-type]
        content=m.content,
        attachments=[MessageAttachment(**a) for a in (m.attachments or [])],
        created_at=m.created_at,
    )


async def _ensure_session_owned(
    db: AsyncSession, user: User, session_id: str
) -> ChatSession:
    """获取会话并校验归属；不存在 → 404，不属于本人 → 403."""
    session = await db.get(ChatSession, session_id)
    if session is None:
        raise NotFoundError(code=40401, message="会话不存在")
    if session.user_id != user.id:
        raise ForbiddenError(code=40301, message="无权访问该会话")
    return session


async def _find_active_session(db: AsyncSession, user: User) -> ChatSession | None:
    """返回最近一条 24h 内的活跃会话；找不到返回 None."""
    threshold = datetime.now(UTC) - timedelta(hours=ACTIVE_SESSION_HOURS)
    # last_message_at 可能为空（用户刚建但没发消息），用 coalesce(last_message_at, created_at)
    activity = func.coalesce(ChatSession.last_message_at, ChatSession.created_at)
    stmt = (
        select(ChatSession)
        .where(ChatSession.user_id == user.id)
        .where(activity >= threshold)
        .order_by(activity.desc())
        .limit(1)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def _validate_context_analysis(
    db: AsyncSession, user: User, analysis_id: str
) -> SwingAnalysis:
    """校验 context_analysis_id 存在且属于当前用户。"""
    analysis = await db.get(SwingAnalysis, analysis_id)
    if analysis is None:
        raise NotFoundError(code=40401, message="分析记录不存在")
    if analysis.user_id != user.id:
        raise ForbiddenError(code=40301, message="无权访问该分析")
    if analysis.deleted_at is not None:
        raise NotFoundError(code=40401, message="分析记录不存在")
    return analysis


# ==================== 创建 / 获取会话 ====================
async def create_or_get_session(
    *, user: User, payload: CreateSessionRequest, db: AsyncSession
) -> CreateSessionResponse:
    """创建或复用活跃会话。

    规则：
    - 传了 `context_analysis_id` → **总是新建**（校验分析归属）
    - 没传 → 24h 内有活跃会话则复用；否则新建
    """
    if payload.context_analysis_id is not None:
        await _validate_context_analysis(db, user, payload.context_analysis_id)
        session = await _create_session(
            db, user, context_analysis_id=payload.context_analysis_id
        )
        messages: list[ChatMessage] = []
    else:
        existing = await _find_active_session(db, user)
        if existing is not None:
            session = existing
            messages = await _list_session_messages(db, session.id, limit=50)
        else:
            session = await _create_session(db, user, context_analysis_id=None)
            messages = []

    return CreateSessionResponse(
        session_id=session.id,
        context_analysis_id=session.context_analysis_id,
        messages=[_to_item(m) for m in messages],
        created_at=session.created_at,
    )


async def _create_session(
    db: AsyncSession, user: User, *, context_analysis_id: str | None
) -> ChatSession:
    session = ChatSession(
        id=new_id("chat"),
        user_id=user.id,
        context_analysis_id=context_analysis_id,
        message_count=0,
    )
    db.add(session)
    await db.flush()
    return session


# ==================== 会话列表 ====================
async def list_sessions(
    *, user: User, page: int, page_size: int, db: AsyncSession
) -> PageData[ChatSessionListItem]:
    activity = func.coalesce(ChatSession.last_message_at, ChatSession.created_at)
    base = select(ChatSession).where(ChatSession.user_id == user.id)
    total = (
        await db.execute(
            select(func.count()).select_from(base.subquery())
        )
    ).scalar_one()

    stmt = (
        base.order_by(activity.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(stmt)).scalars().all()

    items: list[ChatSessionListItem] = []
    for s in rows:
        preview = await _last_message_preview(db, s.id)
        items.append(
            ChatSessionListItem(
                id=s.id,
                context_analysis_id=s.context_analysis_id,
                last_message_preview=preview,
                last_message_at=s.last_message_at,
                message_count=s.message_count,
                created_at=s.created_at,
            )
        )
    return page_data(items, total=total, page=page, page_size=page_size)


async def _last_message_preview(db: AsyncSession, session_id: str) -> str | None:
    stmt = (
        select(ChatMessage.content)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(1)
    )
    content = (await db.execute(stmt)).scalar_one_or_none()
    if content is None:
        return None
    return content[:PREVIEW_MAX_LEN]


# ==================== 会话消息历史 ====================
async def get_session_messages(
    *, user: User, session_id: str, page: int, page_size: int, db: AsyncSession
) -> PageData[ChatMessageItem]:
    await _ensure_session_owned(db, user, session_id)

    total_stmt = select(func.count(ChatMessage.id)).where(
        ChatMessage.session_id == session_id
    )
    total = (await db.execute(total_stmt)).scalar_one()

    stmt = (
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(stmt)).scalars().all()
    items = [_to_item(m) for m in rows]
    return page_data(items, total=total, page=page, page_size=page_size)


async def _list_session_messages(
    db: AsyncSession, session_id: str, *, limit: int = 50
) -> list[ChatMessage]:
    stmt = (
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
        .limit(limit)
    )
    return list((await db.execute(stmt)).scalars().all())


# ==================== 删除会话 ====================
async def delete_session(
    *, user: User, session_id: str, db: AsyncSession
) -> None:
    session = await _ensure_session_owned(db, user, session_id)
    # CASCADE 会自动带走 messages（见 ChatSession.messages.cascade）
    await db.delete(session)
    await db.flush()


# ==================== 发送消息：T2 真正接入 LLM + SSE 流 ====================
HISTORY_WINDOW = 20  # 发给 LLM 的最大历史消息条数（user+assistant 合计）

# drill_card heuristic 关键词 → drill_id 的映射
# 只在 LLM 自然语言回复里命中任一关键词时，才追加 attachment；避免强行造假。
# 真正让 LLM 通过 function call / JSON 输出 drill_id 是 W6 的事。
# 与 `client/src/constants/drillLibrary.ts` 13 drill 同步；命中任一关键词即附 drill_card + video_card
_DRILL_KEYWORDS: list[tuple[tuple[str, ...], str, str]] = [
    (("毛巾", "夹臂", "towel"), "drill_towel_arm", "毛巾夹臂练习"),
    (("击球包", "impact bag", "impact_bag"), "drill_impact_bag", "击球包练习"),
    (("半挥", "半挥杆", "half swing", "half_swing"), "drill_half_swing", "半挥杆节奏练习"),
    (("内侧下杆", "内侧路径", "inside path", "inside_path"), "drill_inside_path", "内侧下杆路径练习"),
    (("臀贴墙", "贴墙", "wall butt", "wall_butt"), "drill_wall_butt", "臀贴墙练习"),
    (("髋部旋转", "髋旋转", "hip rotation", "hip_rotation"), "drill_hip_rotation", "髋部旋转练习"),
    (("镜前", "脊柱角度", "mirror spine", "mirror_spine"), "drill_mirror_spine", "镜前脊柱角度练习"),
    (
        ("重心转移", "留身", "hanging back", "weight shift", "weight_shift"),
        "drill_weight_shift",
        "重心转移节奏练习",
    ),
    (
        ("上杆截停", "截停", "backswing stop", "backswing_stop"),
        "drill_backswing_stop",
        "上杆截停练习",
    ),
    (("充分转肩", "转肩练习", "shoulder turn", "shoulder_turn"), "drill_shoulder_turn", "充分转肩练习"),
    (("挥杆平面", "平面板", "plane board", "plane_board"), "drill_plane_board", "挥杆平面板练习"),
    (("瞄准杆", "站位练习", "alignment stick", "alignment_stick"), "drill_alignment_stick", "瞄准杆站位练习"),
    (("握杆检查", "握杆练习", "grip checkpoint", "grip_checkpoint"), "drill_grip_checkpoint", "握杆检查点练习"),
]


def _detect_drill_attachments(reply_text: str) -> list[dict]:
    """扫回复文本，按关键词推断是否插入 drill_card attachment。

    规则：每个 drill 最多插一张；若命中多个 drill，全都插。
    附件字段与前端 `AnalysisRecommendation` 同构（name+drill_id），
    最少集合即可让 T4 的前端渲染出"训练卡片"。
    """
    attachments: list[dict] = []
    lowered = reply_text.lower()
    for keywords, drill_id, name in _DRILL_KEYWORDS:
        if any(kw.lower() in lowered for kw in keywords):
            attachments.append(
                {
                    "type": "drill_card",
                    "drill_id": drill_id,
                    "name": name,
                }
            )
    return attachments


def _video_cards_for_drills(drill_attachments: list[dict]) -> list[dict]:
    """与 drill_card 成对插入 video_card（v1.1.1）。"""
    videos: list[dict] = []
    for att in drill_attachments:
        if att.get("type") != "drill_card":
            continue
        drill_id = att.get("drill_id")
        if not drill_id:
            continue
        videos.append(
            {
                "type": "video_card",
                "drill_id": drill_id,
                "title": f"{att.get('name', '练习')} · 动作参考",
            }
        )
    return videos


def _detect_reply_attachments(reply_text: str) -> list[dict]:
    drills = _detect_drill_attachments(reply_text)
    return drills + _video_cards_for_drills(drills)


async def _build_llm_messages(
    *,
    db: AsyncSession,
    user: User,
    session: ChatSession,
    user_message_content: str,
    history: list[ChatMessage],
) -> tuple[list[dict[str, str]], str]:
    """构造 LLM 输入 messages：system + 最近 N 条历史 + 当前 user message。

    返回 `(messages, system_prompt_version_used)`。
    """
    recent_analyses = await load_recent_analyses(db, user)
    # P2-M9-04：仅在 PHASE2_PROFILE_V2_ENABLED 时拉取 V2 画像并注入 prompt
    profile_v2 = None
    if settings.PHASE2_PROFILE_V2_ENABLED:
        try:
            profile_v2 = await user_profile_v2_service.get_profile(db, user.id)
        except Exception:  # 防御：V2 表暂未迁移 / service 异常都退回 V1
            profile_v2 = None
    system_prompt = build_system_prompt(user, recent_analyses, profile_v2=profile_v2)

    llm_messages: list[dict[str, str]] = [
        {"role": "system", "content": system_prompt},
    ]
    for h in history[-HISTORY_WINDOW:]:
        # 过滤掉 attachments；LLM 只需要纯文本上下文
        if h.role in ("user", "assistant") and h.content:
            llm_messages.append({"role": h.role, "content": h.content})
    llm_messages.append({"role": "user", "content": user_message_content})
    return llm_messages, SYSTEM_PROMPT_VERSION


async def prepare_turn(
    *, db: AsyncSession, user: User, session_id: str, content: str
) -> PreparedTurn:
    """发消息前置流程（同步/流式共用；**必须在 SSE 开流前调用**）:

    1. 权限校验（40401 / 40301）
    2. 内容安全（40017）
    3. P-02 话题边界：偏离话题 → 固定引导回复，**不扣配额、不调 LLM**
    4. 配额扣减（40007）
    5. 落 user_message（flush 让后续 _list 能看到）
    6. 拉历史 + 构造 LLM messages

    为什么不在 stream_message 里做这些？因为 `StreamingResponse` 一旦开始写
    response，就没法再用标准异常处理器把 40401/40301 翻成 JSON error 响应了
    （会抛 "Caught handled exception, but response already started"）。
    所以 API 层要先调 `prepare_turn`，抛任何 AppException 时仍是普通 HTTP 响应。

    返回 ``PreparedTurn``；若 ``boundary_assistant`` 非空，调用方应走边界回复路径。
    """
    session = await _ensure_session_owned(db, user, session_id)

    # P1-C1：内容审核必须发生在配额扣减**之前**——违规消息不应该消耗配额，
    # 否则用户每次写错话都"白扣一次额度"。
    wx_oid = user.wechat_openid or user.wechat_app_openid or ""
    sec_result = await wechat_check_text(content, openid=wx_oid)
    if not sec_result.passed:
        raise BadRequestError(
            code=40017,
            message=sec_result.reason or "内容涉嫌违规，请调整后重试",
        )

    refusal = topic_boundary_refusal_for(classify_user_message(content))
    if refusal is not None:
        quota = await quota_service.get_or_create_chat_quota(db, user)
        user_msg = ChatMessage(
            id=new_id("msg"),
            session_id=session.id,
            role="user",
            content=content,
            attachments=[],
        )
        assistant_msg = ChatMessage(
            id=new_id("msg"),
            session_id=session.id,
            role="assistant",
            content=refusal,
            attachments=[],
        )
        db.add(user_msg)
        db.add(assistant_msg)
        session.last_message_at = datetime.now(UTC)
        session.message_count = (session.message_count or 0) + 2
        await db.flush()
        return PreparedTurn(
            session=session,
            user_msg=user_msg,
            quota=quota,
            llm_messages=[],
            boundary_assistant=assistant_msg,
        )

    quota = await quota_service.consume_chat_quota(db, user)

    user_msg = ChatMessage(
        id=new_id("msg"),
        session_id=session.id,
        role="user",
        content=content,
        attachments=[],
    )
    db.add(user_msg)
    await db.flush()

    # 拉历史时排除本条新 user_msg（我们会显式把它放在 messages 最后）
    all_msgs = await _list_session_messages(db, session.id, limit=HISTORY_WINDOW + 1)
    history = [m for m in all_msgs if m.id != user_msg.id]

    llm_messages, prompt_version = await _build_llm_messages(
        db=db,
        user=user,
        session=session,
        user_message_content=content,
        history=history,
    )
    # 首次或升版时写入 session
    if session.system_prompt_version != prompt_version:
        session.system_prompt_version = prompt_version

    return PreparedTurn(
        session=session,
        user_msg=user_msg,
        quota=quota,
        llm_messages=llm_messages,
    )


async def _finalize_success(
    *,
    db: AsyncSession,
    session: ChatSession,
    reply_text: str,
    usage: dict[str, int] | None,
) -> ChatMessage:
    """LLM 成功后：落 assistant_message + 更新 session 元信息."""
    attachments = _detect_reply_attachments(reply_text)
    assistant_msg = ChatMessage(
        id=new_id("msg"),
        session_id=session.id,
        role="assistant",
        content=reply_text,
        attachments=attachments,
        prompt_tokens=(usage or {}).get("prompt_tokens"),
        completion_tokens=(usage or {}).get("completion_tokens"),
    )
    db.add(assistant_msg)
    session.last_message_at = datetime.now(UTC)
    session.message_count = (session.message_count or 0) + 2
    await db.flush()
    return assistant_msg


async def _finalize_llm_error(
    *,
    db: AsyncSession,
    session: ChatSession,
    user_msg: ChatMessage,
    quota: Any,
    partial_text: str,
    error_message: str,
) -> None:
    """LLM 失败后：退配额 + 落一条带"回复中断"标记的 assistant_message（若有部分内容）.

    注意：**不抛异常**，让 SSE 发送方优雅结束；同步版会再抛 AIChatServiceError。
    """
    await quota_service.refund_chat_quota(db, quota)
    if partial_text:
        # 有部分内容，保留下来并追加中断说明
        assistant_msg = ChatMessage(
            id=new_id("msg"),
            session_id=session.id,
            role="assistant",
            content=partial_text + "\n\n[回复中断，请稍后重试]",
            attachments=[],
        )
        db.add(assistant_msg)
        session.last_message_at = datetime.now(UTC)
        session.message_count = (session.message_count or 0) + 2
    else:
        # 用户消息已落库但无 AI 回复；只推进 message_count 到 +1
        session.message_count = (session.message_count or 0) + 1
    await db.flush()
    # 不抛（供 SSE 使用）；调用方决定要不要抛
    _ = (user_msg, error_message)  # 预留给后续可能的失败审计落库


# ==================== 同步发消息（T3 前端先走这条 / SSE 降级） ====================
async def send_message_sync(
    *,
    user: User,
    session_id: str,
    content: str,
    db: AsyncSession,
    llm_client: AbstractLLMClient | None = None,
) -> SendMessageResponse:
    """发消息并等 LLM 全部回完再整条返回（非流式 JSON）.

    用途：
    - T3 前端第一版（先 UI 后流式）接入
    - 客户端 `Accept: application/json` 显式降级
    - 测试里不想逐事件解析时方便断言

    LLM 超时/失败 → 退配额 + 抛 `AIChatServiceError(50106)`（外层 API 转 502）。
    """
    from app.core.exceptions import AIChatServiceError

    prepared = await prepare_turn(
        db=db, user=user, session_id=session_id, content=content
    )

    if prepared.boundary_assistant is not None:
        remaining = quota_service.chat_remaining(prepared.quota)
        return SendMessageResponse(
            user_message=_to_item(prepared.user_msg),
            assistant_message=_to_item(prepared.boundary_assistant),
            quota_remaining=remaining,
        )

    session = prepared.session
    user_msg = prepared.user_msg
    quota = prepared.quota
    llm_messages = prepared.llm_messages

    client = llm_client or get_llm_client()
    chunks: list[str] = []
    usage: dict[str, int] | None = None
    error_msg: str | None = None

    try:
        async for chunk in client.stream_chat(llm_messages):
            if chunk.type == "content":
                chunks.append(chunk.delta)
            elif chunk.type == "done":
                usage = chunk.usage
            elif chunk.type == "error":
                error_msg = chunk.error or "LLM 调用失败"
                break
    except Exception as exc:
        error_msg = f"LLM 异常: {exc}"

    partial = "".join(chunks)
    if error_msg is not None:
        await _finalize_llm_error(
            db=db,
            session=session,
            user_msg=user_msg,
            quota=quota,
            partial_text=partial,
            error_message=error_msg,
        )
        raise AIChatServiceError(message=error_msg)

    assistant_msg = await _finalize_success(
        db=db, session=session, reply_text=partial, usage=usage
    )

    # W8-T3：chat_remaining 现已统一在 quota.total<0 时返回 -1，无需再做 fixup
    remaining = quota_service.chat_remaining(quota)

    return SendMessageResponse(
        user_message=_to_item(user_msg),
        assistant_message=_to_item(assistant_msg),
        quota_remaining=remaining,
    )


# ==================== 流式发消息（T2 核心：SSE） ====================
async def stream_boundary_reply(
    *,
    session: ChatSession,
    user_msg: ChatMessage,
    assistant_msg: ChatMessage,
    quota: Any,
) -> AsyncIterator[dict]:
    """P-02：话题边界固定回复，模拟 SSE 事件序列（不调 LLM）。"""
    yield {
        "type": "message_start",
        "user_message_id": user_msg.id,
        "assistant_message_id": assistant_msg.id,
        "user_message": _to_item(user_msg).model_dump(mode="json"),
    }
    yield {"type": "content_delta", "delta": assistant_msg.content}
    remaining = quota_service.chat_remaining(quota)
    yield {
        "type": "message_end",
        "assistant_message_id": assistant_msg.id,
        "content": assistant_msg.content,
        "attachments": [],
        "quota_remaining": remaining,
        "usage": None,
    }


async def stream_message(
    *,
    session: ChatSession,
    user_msg: ChatMessage,
    quota: Any,
    llm_messages: list[dict[str, str]],
    db: AsyncSession,
    llm_client: AbstractLLMClient | None = None,
) -> AsyncIterator[dict]:
    """发消息并以 async generator 形式 yield SSE 事件字典（业务事件，不含 SSE 格式封装）.

    调用方（API 层）必须先调 `prepare_turn` 做好权限校验 + 配额扣减 + 落 user_msg，
    然后把返回的 4 元组原样传进来。**本函数不再抛 40x**；LLM 失败会 yield `error` 事件。

    事件序列（正常情况）：
      1) message_start          携带 user_message / assistant_message_id
      2) content_delta × N      每块 LLM 增量
      3) attachment × 0..K      命中 drill heuristic 时
      4) message_end            携带 assistant_message_id、quota_remaining、usage

    事件序列（失败情况）：
      1) message_start
      2) content_delta × M
      3) error                  code=50106；配额已在此事件前退回

    调用方负责：
    - 把每个 dict 编码成 SSE 帧（`event: ...\\ndata: ...\\n\\n`）
    - 生成器跑完后 commit 数据库
    """
    # 提前生成 assistant message id，方便前端在 message_start 时就占位一条气泡
    assistant_msg_id = new_id("msg")

    yield {
        "type": "message_start",
        "user_message_id": user_msg.id,
        "assistant_message_id": assistant_msg_id,
        "user_message": _to_item(user_msg).model_dump(mode="json"),
    }

    client = llm_client or get_llm_client()
    chunks: list[str] = []
    usage: dict[str, int] | None = None
    error_msg: str | None = None

    try:
        async for chunk in client.stream_chat(llm_messages):
            if chunk.type == "content":
                chunks.append(chunk.delta)
                yield {"type": "content_delta", "delta": chunk.delta}
            elif chunk.type == "done":
                usage = chunk.usage
            elif chunk.type == "error":
                error_msg = chunk.error or "LLM 调用失败"
                break
    except Exception as exc:
        error_msg = f"LLM 异常: {exc}"

    partial = "".join(chunks)

    if error_msg is not None:
        await _finalize_llm_error(
            db=db,
            session=session,
            user_msg=user_msg,
            quota=quota,
            partial_text=partial,
            error_message=error_msg,
        )
        yield {
            "type": "error",
            "code": 50106,
            "message": "AI 教练暂时开小差了，请稍后再试",
            "detail": error_msg,
        }
        return

    # ====== 成功路径 ======
    # attachments 先算出来，并在落库前通过 attachment 事件推送给前端
    attachments = _detect_reply_attachments(partial)
    for att in attachments:
        yield {"type": "attachment", "attachment": att}

    # 覆盖 assistant_msg_id（让落库的 id 与推送的 id 一致）
    assistant_msg = ChatMessage(
        id=assistant_msg_id,
        session_id=session.id,
        role="assistant",
        content=partial,
        attachments=attachments,
        prompt_tokens=(usage or {}).get("prompt_tokens"),
        completion_tokens=(usage or {}).get("completion_tokens"),
    )
    db.add(assistant_msg)
    session.last_message_at = datetime.now(UTC)
    session.message_count = (session.message_count or 0) + 2
    await db.flush()

    # W8-T3：chat_remaining 现已统一在 quota.total<0 时返回 -1，无需再做 fixup
    remaining = quota_service.chat_remaining(quota)

    yield {
        "type": "message_end",
        "assistant_message_id": assistant_msg.id,
        "content": partial,
        "attachments": attachments,
        "quota_remaining": remaining,
        "usage": usage,
    }
