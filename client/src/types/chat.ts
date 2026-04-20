/**
 * 与后端 `app/schemas/chat.py` 对齐的前端类型定义。
 *
 * 注意：
 * - `MessageAttachment` 在后端是 `extra="allow"`；这里定义 **联合类型**，
 *   再加一个兜底 `Record<string, unknown>` 避免未来新 type 阻塞构建。
 * - `quota_remaining = -1` 代表会员无限次；前端 UI 需分支判断。
 */

import type { PageData } from './api'

export type ChatRole = 'user' | 'assistant' | 'system'

/* ==================== 附件 ==================== */
export interface DrillCardAttachment {
  type: 'drill_card'
  drill_id: string
  name: string
  // 后续可能扩展：duration_minutes / sets / description ...
  [key: string]: unknown
}

export interface ImageAttachment {
  type: 'image'
  url: string
  [key: string]: unknown
}

export interface AnalysisCardAttachment {
  type: 'analysis_card'
  analysis_id: string
  overall_score?: number
  [key: string]: unknown
}

export type MessageAttachment =
  | DrillCardAttachment
  | ImageAttachment
  | AnalysisCardAttachment
  // 前向兼容：后端未来新增其它 type 时前端不会立即报类型错
  | { type: string; [key: string]: unknown }

/* ==================== 消息 ==================== */
export interface ChatMessageItem {
  id: string
  role: ChatRole
  content: string
  attachments: MessageAttachment[]
  created_at: string
}

/**
 * UI 侧的消息对象 = 服务端字段 + 前端 transient 标记。
 *
 * transient 字段只用于**渲染态**，不会参与任何发往后端的 payload：
 *   - `streaming`：assistant 气泡正在被 SSE 逐字追加 → 渲染打字光标
 *   - `errored`：流中途 50106 / 网络中断 → 渲染"点击重试"兜底
 *   - `pending`：user 气泡已乐观追加但 HTTP 201/SSE message_start 还没回来 →
 *                发送失败时用于精准回滚
 */
export interface DisplayChatMessage extends ChatMessageItem {
  streaming?: boolean
  errored?: boolean
  pending?: boolean
}

/* ==================== 快捷问题 ==================== */
export interface QuickQuestionItem {
  id: string
  text: string
  requires_analysis: boolean
}

export interface QuickQuestionsResponse {
  questions: QuickQuestionItem[]
}

/* ==================== 会话 ==================== */
export interface CreateSessionRequest {
  context_analysis_id?: string | null
}

export interface CreateSessionResponse {
  session_id: string
  context_analysis_id: string | null
  messages: ChatMessageItem[]
  created_at: string
}

export interface ChatSessionListItem {
  id: string
  context_analysis_id: string | null
  last_message_preview: string | null
  last_message_at: string | null
  message_count: number
  created_at: string
}

export type ChatSessionListResponse = PageData<ChatSessionListItem>
export type ChatMessagesResponse = PageData<ChatMessageItem>

/* ==================== 发送消息（T3 非流式 JSON） ==================== */
export interface SendMessageRequest {
  content: string
  attachments?: MessageAttachment[]
}

export interface SendMessageResponse {
  user_message: ChatMessageItem
  assistant_message: ChatMessageItem
  /** 免费用户剩余轮次；会员返回 -1 表示无限 */
  quota_remaining: number
}
