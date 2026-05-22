"""AI 对话相关 Pydantic schema（对齐 docs/02-API接口设计文档.md §四 /chat）.

范围
----
- M3-T1：会话创建 / 列表 / 历史 / 发消息（**非流式，JSON 返回**）/ 删除 / 快捷问题
- M3-T2：同一批 schema 不变，send_message 升级为 SSE 流式（不再返回 Pydantic，而是
  `StreamingResponse(text/event-stream)`），但**落库后的 Message 结构保持一致**。

T1 阶段的 `MessageAttachment` 支持 `image` / `drill_card` / `analysis_card` / `video_card`；
`video_card` 与 `drill_card` 成对由 heuristic 触发（v1.1.1）；用户侧图片上传仍挂 W7。
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# ==================== 通用 ====================
MessageRole = Literal["user", "assistant", "system"]


class MessageAttachment(BaseModel):
    """AI 回复可携带的附件卡片。MVP 只涉及以下两种类型：

    - ``image``：图片；T1 只保留字段，实际图片上传接口在 W7 做。
    - ``drill_card``：训练练习卡片；M3-T2 起 LLM 回复中 heuristic 命中后插入。
    - ``video_card``：练习示范视频；v1.1.1 起与 ``drill_card`` 成对插入。
    - ``analysis_card``：历史分析报告卡片；前端 v1.1.0 渲染，后端 structured 输出仍 W7 余量。

    为了让前端可按 ``type`` 做类型分支，这里放宽到 extra="allow" —— 不同类型的附件
    有不同的字段（drill_card 有 `drill_id` / `name`；image 有 `url`），各自自描述。
    """

    model_config = ConfigDict(extra="allow")

    type: Literal["image", "drill_card", "analysis_card", "video_card"]


# ==================== 4.6 GET /v1/chat/quick-questions ====================
class QuickQuestionItem(BaseModel):
    id: str
    text: str
    requires_analysis: bool = Field(
        default=False,
        description="为 true 时前端需校验用户至少有一次分析记录",
    )


class QuickQuestionsResponse(BaseModel):
    questions: list[QuickQuestionItem]


# ==================== 4.1 POST /v1/chat/sessions ====================
class CreateSessionRequest(BaseModel):
    """创建或获取活跃会话。

    逻辑：
    - 无入参 / `context_analysis_id=None`：如果 24h 内有未删除会话则复用，否则新建
    - 有 `context_analysis_id`：总是**新建会话**（保证分析与会话一一对应），
      并把该分析作为"上下文锚点"注入 system prompt（T2 实现真正注入）
    """

    context_analysis_id: str | None = Field(
        default=None,
        max_length=32,
        description="关联的挥杆分析 ID；有值则总是新建会话，绑定该分析为上下文",
    )


class ChatMessageItem(BaseModel):
    """落库后的一条消息（前后端通用结构）."""

    id: str
    role: MessageRole
    content: str
    attachments: list[MessageAttachment] = Field(default_factory=list)
    created_at: datetime


class CreateSessionResponse(BaseModel):
    session_id: str
    context_analysis_id: str | None = None
    # 返回当前历史消息列表（对于新建会话即只有一条 system-style 的欢迎语；复用时是完整历史）
    messages: list[ChatMessageItem] = Field(default_factory=list)
    created_at: datetime


# ==================== 4.2 POST /v1/chat/sessions/{id}/messages ====================
class SendMessageRequest(BaseModel):
    """发送消息。

    - 仅支持纯文本（MVP）；图片消息挂 W7。
    - 内容 1-500 字，与 docs/02 §4.2 对齐。
    """

    content: str = Field(..., min_length=1, max_length=500)
    # T2 再启用；T1 先保留字段但忽略
    attachments: list[MessageAttachment] = Field(default_factory=list)


class SendMessageResponse(BaseModel):
    """非流式回复（T1）.

    T2 升级为 SSE 后此 schema 只在 `Accept: application/json` 降级路径里使用
    （供前端 T3 提前接入）。返回的是整条 assistant message（已落库）。
    """

    user_message: ChatMessageItem
    assistant_message: ChatMessageItem
    quota_remaining: int  # 回复完成后的剩余轮次（免费用户），-1 代表无限


# ==================== 4.3 GET /v1/chat/sessions/{id}/messages ====================
# 分页响应复用 `PageData[ChatMessageItem]`，不再定义单独 schema


# ==================== 4.4 GET /v1/chat/sessions ====================
class ChatSessionListItem(BaseModel):
    id: str
    context_analysis_id: str | None = None
    last_message_preview: str | None = Field(
        default=None,
        description="最后一条消息内容前 100 字（便于会话列表预览）",
    )
    last_message_at: datetime | None = None
    message_count: int
    created_at: datetime


# ==================== 辅助：配额快照（发消息响应里嵌入） ====================
class ChatQuotaSnapshot(BaseModel):
    """快捷问题接口可顺带返回配额，减少客户端一次请求."""

    remaining: int  # -1 = 无限
    total: int  # -1 = 无限
    used: int
