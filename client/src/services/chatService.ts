/**
 * AI 对话相关接口封装（与后端 `/v1/chat/*` 对齐）。
 *
 * T3 阶段只用 **非流式 JSON** 路径：
 * - 请求 `Accept: application/json` + body `content` → 后端走 `send_message_sync`
 * - T4 升级流式时新增 `streamMessage`，但此 `sendMessage` 仍保留给兜底 / 测试用
 *
 * 为什么每次请求都显式加 `Accept: application/json`？
 * - 后端判 SSE 的条件是 `Accept: text/event-stream` 或 `?stream=true`；
 * - 小程序 `Taro.request` 默认可能带 Accept 通配符（星斜星），虽然不会触发 SSE，
 *   但显式写 `application/json` 更稳，也让抓包排查时意图一目了然。
 */

import type {
  ChatMessageItem,
  ChatMessagesResponse,
  ChatSessionListResponse,
  CreateSessionRequest,
  CreateSessionResponse,
  MessageAttachment,
  QuickQuestionsResponse,
  SendMessageRequest,
  SendMessageResponse,
} from '@/types/chat'
import { streamSSE, type StreamCancel } from '@/utils/sseClient'
import { http } from './request'

const ACCEPT_JSON = { Accept: 'application/json' }

/* ==================== 流式事件类型（与后端 _sse_event_stream 对齐） ==================== */
export interface StreamStartEvent {
  user_message_id: string
  assistant_message_id: string
  user_message: ChatMessageItem
}

export interface StreamDeltaEvent {
  delta: string
}

export interface StreamAttachmentEvent {
  attachment: MessageAttachment
}

export interface StreamEndEvent {
  assistant_message_id: string
  content: string
  attachments: MessageAttachment[]
  quota_remaining: number
  usage?: { prompt_tokens?: number; completion_tokens?: number } | null
}

export interface StreamErrorEvent {
  code: number
  message: string
  detail?: string
}

export interface StreamHandlers {
  onStart(event: StreamStartEvent): void
  onDelta(event: StreamDeltaEvent): void
  onAttachment(event: StreamAttachmentEvent): void
  onEnd(event: StreamEndEvent): void
  /**
   * 业务 error 事件（后端通过 SSE `event: error` 发出的 50106）。
   * 注意：网络 / 连接层错误走 `onTransportError`，二者分流的原因：
   *   - 业务 error：用户消息已入库、配额已退，UI 应提示"AI 开小差"
   *   - 传输错误：可能根本没到后端，UI 需要"重试"而不是"配额退了请再问"
   */
  onBusinessError(event: StreamErrorEvent): void
  onTransportError(err: Error, meta: { aborted: boolean }): void
  /** 正常结束（message_end 收到后紧跟着） */
  onClose?(): void
}

export const chatService = {
  /** 4.6 获取快捷问题（后端允许匿名；未登录时也能调） */
  getQuickQuestions() {
    return http.get<QuickQuestionsResponse>('/chat/quick-questions', {
      noAuth: true,
      timeout: 60000,
    })
  },

  /**
   * 4.1 创建 / 获取活跃会话。
   *
   * 后端约定：
   * - `context_analysis_id` 有值时**总是新建**（保证分析与会话一一对应）
   * - 不传时 24h 内若有未删除的活跃会话则复用，否则新建
   */
  createSession(payload: CreateSessionRequest = {}) {
    return http.post<CreateSessionResponse>('/chat/sessions', payload)
  },

  /** 4.4 会话列表（T3 不用，保留给 T6 历史页） */
  listSessions(params: { page?: number; page_size?: number } = {}) {
    const qs = new URLSearchParams()
    if (params.page) qs.set('page', String(params.page))
    if (params.page_size) qs.set('page_size', String(params.page_size))
    const suffix = qs.toString()
    return http.get<ChatSessionListResponse>(
      `/chat/sessions${suffix ? `?${suffix}` : ''}`,
    )
  },

  /** 4.3 会话历史消息分页 */
  getMessages(
    sessionId: string,
    params: { page?: number; page_size?: number } = {},
  ) {
    const qs = new URLSearchParams()
    if (params.page) qs.set('page', String(params.page))
    if (params.page_size) qs.set('page_size', String(params.page_size))
    const suffix = qs.toString()
    return http.get<ChatMessagesResponse>(
      `/chat/sessions/${sessionId}/messages${suffix ? `?${suffix}` : ''}`,
      { timeout: 60000 },
    )
  },

  /**
   * 4.2 发送消息（T3 非流式）。
   *
   * 关键点：
   * - `Accept: application/json` 强制走 JSON 分支
   * - 加 `?stream=false` 双保险，后端即使未来改默认值也不会误走 SSE
   * - timeout=185s：与 app.config.ts networkTimeout.request + 服务端 LLM 窗对齐；
   *   单靠调大仍会受微信客户端策略影响，SSE 链路已配合服务端 sse-ping 保活帧。
   * - silent=true：业务错误码（40007 配额耗尽、40009 速率限制、50106 LLM 失败）
   *   交给 UI 层自己 toast / 做兜底 UI，避免重复弹"请求失败"
   */
  sendMessage(sessionId: string, payload: SendMessageRequest) {
    return http.post<SendMessageResponse>(
      `/chat/sessions/${sessionId}/messages?stream=false`,
      payload,
      { header: ACCEPT_JSON, timeout: 185000, silent: true },
    )
  },

  /**
   * 4.2 发送消息（T4 流式）。
   *
   * 事件序列：
   *   message_start → content_delta × N → [attachment × K] → message_end
   *   或：message_start → content_delta × M → error
   *
   * 返回 cancel 函数；页面销毁 / 用户清空对话时调用可立即中断连接。
   */
  streamMessage(
    sessionId: string,
    payload: SendMessageRequest,
    handlers: StreamHandlers,
  ): StreamCancel {
    return streamSSE(
      {
        url: `/chat/sessions/${sessionId}/messages?stream=true`,
        method: 'POST',
        body: payload,
        // 须 ≥ 后端 LLM_STREAM read 超时 + 网络余量（默认服务端 120s）
        timeoutMs: 180000,
      },
      {
        onEvent: (evt) => {
          switch (evt.type) {
            case 'message_start':
              handlers.onStart(evt.data as StreamStartEvent)
              break
            case 'content_delta':
              handlers.onDelta(evt.data as StreamDeltaEvent)
              break
            case 'attachment':
              handlers.onAttachment(evt.data as StreamAttachmentEvent)
              break
            case 'message_end':
              handlers.onEnd(evt.data as StreamEndEvent)
              handlers.onClose?.()
              break
            case 'error':
              handlers.onBusinessError(evt.data as StreamErrorEvent)
              break
            // 其它事件（message / ping）忽略
          }
        },
        onError: (err, meta) => handlers.onTransportError(err, meta),
        // 仅在后端 `event: error` 没发但连接就自然关闭时兜底；正常路径由 onEnd 调 onClose
        onDone: () => handlers.onClose?.(),
      },
    )
  },

  /** 4.7 删除会话（硬删；后端 CASCADE 带走 messages） */
  deleteSession(sessionId: string) {
    return http.del<null>(`/chat/sessions/${sessionId}`)
  },
}
