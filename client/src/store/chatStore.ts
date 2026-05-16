/**
 * AI 对话全局状态（Zustand）
 *
 * T3：非流式 submitMessage
 * T4：流式 submitMessage（默认）+ submitMessageSync（兜底 / 测试）
 *
 * 流式发送的关键不变量：
 *   - 乐观插入 user 气泡 + assistant streaming 占位；任何阶段失败都要**回滚**这两条
 *   - `message_start` 到达后把 assistant 占位的 id 替换成服务端 id，方便历史拉取去重
 *   - `content_delta` 只追加到"最后一条 assistant streaming 气泡"的 content
 *   - `message_end` 标记 streaming=false；如果后端加了 attachments，覆盖一次（以后端为准）
 *   - SSE 业务 `error` 事件：assistant 气泡改 errored=true；user 气泡保留（后端已落库）
 *   - 传输层错误：assistant / user 两条占位都回滚（无法确定后端是否已落）
 */

import { create } from 'zustand'
import { describePageLoadFailure, isRequestError } from '@/services/request'
import { chatService } from '@/services/chatService'
import {
  weappSupportsChunkedStreaming,
  type StreamCancel,
} from '@/utils/sseClient'
import type {
  DisplayChatMessage,
  MessageAttachment,
  QuickQuestionItem,
} from '@/types/chat'
import type { UserQuota } from '@/types/api'

/** 业务错误码（对齐 docs/02） */
const ERR_CHAT_QUOTA_EXHAUSTED = 40007
const ERR_RATE_LIMIT = 40009
// P1-C1：用户消息被微信内容安全 (msg_sec_check) 判定为违规
const ERR_CONTENT_VIOLATION = 40017
const ERR_CHAT_SERVICE = 50106

export type ChatQuotaSnapshot = {
  /** -1 = 会员无限；0..N = 剩余轮次 */
  remaining: number
  total: number
}

export type SubmitMessageError =
  | { kind: 'quota_exhausted' }
  | { kind: 'rate_limit' }
  | { kind: 'content_violation'; message: string }
  | { kind: 'service_error'; message: string }
  | { kind: 'network'; message: string }

interface ChatState {
  /* ---------- 数据 ---------- */
  currentSessionId: string | null
  contextAnalysisId: string | null
  messages: DisplayChatMessage[]
  quickQuestions: QuickQuestionItem[]
  quota: ChatQuotaSnapshot

  /* ---------- UI 辅助状态 ---------- */
  loading: boolean
  sending: boolean
  bootstrapError: string | null
  /** 当前活跃的流式连接；clearSession/unmount 时需要 abort */
  activeStream: StreamCancel | null

  /* ---------- Actions ---------- */
  bootstrapSession(contextAnalysisId?: string | null): Promise<void>
  /** 从对话历史进入：加载已有 session 与消息 */
  bootstrapExistingSession(
    sessionId: string,
    contextAnalysisId?: string | null,
  ): Promise<void>
  /** T4 默认：流式发送 */
  submitMessage(content: string): Promise<void>
  /** 兜底：非流式 JSON 版本（保留给 E2E 测试 / 微信极老版本） */
  submitMessageSync(content: string): Promise<void>
  clearSession(): Promise<void>
  hydrateQuotaFromUser(userQuota: UserQuota | null | undefined): void
  cancelActiveStream(): void
  reset(): void
}

function initialQuota(): ChatQuotaSnapshot {
  return { remaining: -1, total: -1 }
}

function localId(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`
}

export const useChatStore = create<ChatState>((set, get) => ({
  currentSessionId: null,
  contextAnalysisId: null,
  messages: [],
  quickQuestions: [],
  quota: initialQuota(),
  loading: false,
  sending: false,
  bootstrapError: null,
  activeStream: null,

  hydrateQuotaFromUser(userQuota) {
    if (!userQuota) return
    set({
      quota: {
        remaining: userQuota.chat_remaining_today,
        total: userQuota.chat_total_today,
      },
    })
  },

  async bootstrapSession(contextAnalysisId) {
    set({ loading: true, bootstrapError: null })
    try {
      const [quickResp, sessionResp] = await Promise.all([
        chatService.getQuickQuestions(),
        chatService.createSession(
          contextAnalysisId ? { context_analysis_id: contextAnalysisId } : {},
        ),
      ])

      set({
        currentSessionId: sessionResp.session_id,
        contextAnalysisId: sessionResp.context_analysis_id,
        messages: sessionResp.messages as DisplayChatMessage[],
        quickQuestions: quickResp.questions,
        loading: false,
      })
    } catch (err) {
      const msg = describePageLoadFailure(err)
      set({ loading: false, bootstrapError: msg })
      throw err
    }
  },

  async bootstrapExistingSession(sessionId, contextAnalysisId) {
    set({ loading: true, bootstrapError: null })
    try {
      const [quickResp, msgResp] = await Promise.all([
        chatService.getQuickQuestions(),
        chatService.getMessages(sessionId, { page: 1, page_size: 100 }),
      ])
      const items = (msgResp.items || []).map((m) => ({
        ...m,
        attachments: m.attachments || [],
      })) as DisplayChatMessage[]
      set({
        currentSessionId: sessionId,
        contextAnalysisId: contextAnalysisId ?? null,
        messages: items,
        quickQuestions: quickResp.questions,
        loading: false,
      })
    } catch (err) {
      const msg = describePageLoadFailure(err)
      set({ loading: false, bootstrapError: msg })
      throw err
    }
  },

  /* ============================== 发送 ==============================
   *
   * **微信小程序（真机）**：同步 JSON 等整条 LLM 往往超过 wx.request ~60s 上限 → 在支持
   * `enableChunked` 时**默认走 SSE**（后端 `sse-ping` 保活）。
   *
   * **RN / H5**：`TARO_APP_CHAT_USE_SSE=true` 启用流式，否则同步 JSON。
   *
   * **调试**：`TARO_APP_CHAT_FORCE_SYNC=true` 强制同步 JSON（真机长对话仍可能超时）。
   */
  submitMessage(content) {
    const env = typeof process !== 'undefined' ? process.env : undefined
    const isWeappMiniprogram = env?.TARO_ENV === 'weapp'
    const forceSync = env?.TARO_APP_CHAT_FORCE_SYNC === 'true'

    if (isWeappMiniprogram && !forceSync && weappSupportsChunkedStreaming()) {
      return submitMessageStreamImpl(get, set, content)
    }

    const sseRequested = env?.TARO_APP_CHAT_USE_SSE === 'true'
    const useSSE = sseRequested && !isWeappMiniprogram
    if (!useSSE) {
      return get().submitMessageSync(content)
    }
    return submitMessageStreamImpl(get, set, content)
  },

  /* ============================== 非流式（默认路径） ============================== */
  async submitMessageSync(content) {
    const text = content.trim()
    if (!text) {
      console.log('[chat] submitMessageSync: empty text, skip')
      return
    }
    if (text.length > 500) throw new Error('单条消息最多 500 字')
    const { currentSessionId, sending } = get()
    console.log('[chat] submitMessageSync ENTER', {
      len: text.length,
      sessionId: currentSessionId,
      sending,
    })
    if (!currentSessionId) throw new Error('会话未就绪，请稍后再试')
    if (sending) {
      console.warn('[chat] sending=true 已经有请求在飞，本次跳过')
      return
    }

    const userPendingId = localId('msg-user')
    const assistantPendingId = localId('msg-ai')
    const now = new Date().toISOString()
    const pendingUser: DisplayChatMessage = {
      id: userPendingId,
      role: 'user',
      content: text,
      attachments: [],
      created_at: now,
      pending: true,
    }
    // 乐观插入"AI 正在思考"占位（content='' + streaming=true）
    // 让 page 的"三点跳动"提示能正常显示。
    const pendingAssistant: DisplayChatMessage = {
      id: assistantPendingId,
      role: 'assistant',
      content: '',
      attachments: [],
      created_at: now,
      streaming: true,
      pending: true,
    }
    set({
      sending: true,
      messages: [...get().messages, pendingUser, pendingAssistant],
    })

    try {
      console.log('[chat] HTTP POST start')
      const resp = await chatService.sendMessage(currentSessionId, {
        content: text,
      })
      console.log('[chat] HTTP POST OK', {
        user_message_id: resp?.user_message?.id,
        assistant_message_id: resp?.assistant_message?.id,
        assistant_preview: (resp?.assistant_message?.content || '').slice(0, 40),
        quota_remaining: resp?.quota_remaining,
      })
      set((state) => ({
        messages: [
          ...state.messages.filter(
            (m) => m.id !== userPendingId && m.id !== assistantPendingId,
          ),
          resp.user_message as DisplayChatMessage,
          resp.assistant_message as DisplayChatMessage,
        ],
        quota: { ...state.quota, remaining: resp.quota_remaining },
        sending: false,
      }))
      console.log('[chat] state updated, total messages =', get().messages.length)
    } catch (err) {
      console.error('[chat] HTTP POST FAILED', err)
      set((state) => ({
        messages: state.messages.filter(
          (m) => m.id !== userPendingId && m.id !== assistantPendingId,
        ),
        sending: false,
      }))
      throw mapSubmitError(err)
    }
  },

  cancelActiveStream() {
    const { activeStream } = get()
    if (activeStream) {
      activeStream()
      set({ activeStream: null, sending: false })
    }
  },

  async clearSession() {
    const { currentSessionId, activeStream } = get()
    if (activeStream) activeStream()
    if (!currentSessionId) {
      set({ activeStream: null, sending: false })
      return
    }
    try {
      await chatService.deleteSession(currentSessionId)
    } finally {
      set({
        currentSessionId: null,
        contextAnalysisId: null,
        messages: [],
        activeStream: null,
        sending: false,
      })
    }
  },

  reset() {
    const { activeStream } = get()
    if (activeStream) activeStream()
    set({
      currentSessionId: null,
      contextAnalysisId: null,
      messages: [],
      quickQuestions: [],
      quota: initialQuota(),
      loading: false,
      sending: false,
      bootstrapError: null,
      activeStream: null,
    })
  },
}))

/* ==================== 错误映射 ==================== */
function mapSubmitError(err: unknown): Error & {
  submitError: SubmitMessageError
  chatCause?: unknown
} {
  const message = err instanceof Error ? err.message : '网络异常'
  const code = isRequestError(err) ? err.code : undefined
  let submitError: SubmitMessageError
  if (code === ERR_CHAT_QUOTA_EXHAUSTED) {
    submitError = { kind: 'quota_exhausted' }
  } else if (code === ERR_RATE_LIMIT) {
    submitError = { kind: 'rate_limit' }
  } else if (code === ERR_CONTENT_VIOLATION) {
    submitError = { kind: 'content_violation', message }
  } else if (code === ERR_CHAT_SERVICE) {
    submitError = { kind: 'service_error', message }
  } else {
    submitError = { kind: 'network', message }
  }
  return wrapError(message, submitError, err)
}

function wrapError(
  message: string,
  submitError: SubmitMessageError,
  chatCause?: unknown,
): Error & {
  submitError: SubmitMessageError
  chatCause?: unknown
} {
  const wrapped = new Error(message) as Error & {
    submitError: SubmitMessageError
    chatCause?: unknown
  }
  wrapped.submitError = submitError
  if (chatCause !== undefined) {
    wrapped.chatCause = chatCause
  }
  return wrapped
}

export function chatErrorCause(err: unknown): unknown | undefined {
  if (err && typeof err === 'object' && 'chatCause' in err) {
    return (err as { chatCause?: unknown }).chatCause
  }
  return undefined
}

export function getSubmitError(err: unknown): SubmitMessageError | null {
  if (err && typeof err === 'object' && 'submitError' in err) {
    return (err as { submitError: SubmitMessageError }).submitError
  }
  return null
}

export const CHAT_ERROR_CODES = {
  QUOTA_EXHAUSTED: ERR_CHAT_QUOTA_EXHAUSTED,
  RATE_LIMIT: ERR_RATE_LIMIT,
  CONTENT_VIOLATION: ERR_CONTENT_VIOLATION,
  SERVICE_ERROR: ERR_CHAT_SERVICE,
} as const

/* ==================== 流式实现（小程序默认 / RN·H5 由 env 开关） ==================== */
type GetState = () => ChatState
type SetState = (
  partial:
    | Partial<ChatState>
    | ((state: ChatState) => Partial<ChatState>),
) => void

function submitMessageStreamImpl(
  get: GetState,
  set: SetState,
  content: string,
): Promise<void> {
  const text = content.trim()
  if (!text) return Promise.resolve()
  if (text.length > 500) return Promise.reject(new Error('单条消息最多 500 字'))
  const { currentSessionId, sending } = get()
  if (!currentSessionId) return Promise.reject(new Error('会话未就绪，请稍后再试'))
  if (sending) return Promise.resolve()

  const userLocalId = localId('msg-user')
  const assistantLocalId = localId('msg-ai')
  const now = new Date().toISOString()

  const pendingUser: DisplayChatMessage = {
    id: userLocalId,
    role: 'user',
    content: text,
    attachments: [],
    created_at: now,
    pending: true,
  }
  const pendingAssistant: DisplayChatMessage = {
    id: assistantLocalId,
    role: 'assistant',
    content: '',
    attachments: [],
    created_at: now,
    streaming: true,
    pending: true,
  }

  set({
    sending: true,
    messages: [...get().messages, pendingUser, pendingAssistant],
  })

  return new Promise<void>((resolve, reject) => {
    let settled = false
    let sawAnyEvent = false

    const recoverFromHistory = async (): Promise<boolean> => {
      try {
        const resp = await chatService.getMessages(currentSessionId, {
          page: 1,
          page_size: 20,
        })
        const items = resp.items || []
        const lastAssistant = [...items]
          .reverse()
          .find((m) => m.role === 'assistant')
        if (!lastAssistant) return false
        set((state) => ({
          messages: state.messages.map((m, idx) => {
            if (idx !== state.messages.length - 1) return m
            if (m.role !== 'assistant') return m
            return {
              ...m,
              id: lastAssistant.id,
              content: lastAssistant.content,
              attachments: (lastAssistant.attachments ||
                []) as MessageAttachment[],
              streaming: false,
              pending: false,
            }
          }),
        }))
        return true
      } catch (_err) {
        return false
      }
    }

    const markStreamingBubbleErrored = (fallbackText: string) => {
      set((state) => ({
        messages: state.messages.map((m, idx) => {
          if (idx !== state.messages.length - 1) return m
          if (m.role !== 'assistant') return m
          return {
            ...m,
            content: m.content || fallbackText,
            streaming: false,
            errored: true,
          }
        }),
      }))
    }

    const finish = (err?: Error) => {
      if (settled) return
      settled = true
      set({ sending: false, activeStream: null })
      err ? reject(err) : resolve()
    }

    const cancel = chatService.streamMessage(
      currentSessionId,
      { content: text },
      {
        onStart: (evt) => {
          sawAnyEvent = true
          set((state) => ({
            messages: state.messages.map((m) => {
              if (m.id === userLocalId) {
                return {
                  ...(evt.user_message as DisplayChatMessage),
                  pending: false,
                }
              }
              if (m.id === assistantLocalId) {
                return {
                  ...m,
                  id: evt.assistant_message_id,
                  pending: false,
                }
              }
              return m
            }),
          }))
        },

        onDelta: (evt) => {
          sawAnyEvent = true
          set((state) => ({
            messages: state.messages.map((m, idx) =>
              idx === state.messages.length - 1 && m.role === 'assistant'
                ? { ...m, content: m.content + evt.delta }
                : m,
            ),
          }))
        },

        onAttachment: (evt) => {
          sawAnyEvent = true
          set((state) => ({
            messages: state.messages.map((m, idx) =>
              idx === state.messages.length - 1 && m.role === 'assistant'
                ? {
                    ...m,
                    attachments: [
                      ...m.attachments,
                      evt.attachment as MessageAttachment,
                    ],
                  }
                : m,
            ),
          }))
        },

        onEnd: (evt) => {
          sawAnyEvent = true
          set((state) => ({
            quota: { ...state.quota, remaining: evt.quota_remaining },
            messages: state.messages.map((m, idx) => {
              if (idx !== state.messages.length - 1) return m
              if (m.role !== 'assistant') return m
              return {
                ...m,
                id: evt.assistant_message_id,
                content: evt.content || m.content,
                attachments: evt.attachments?.length
                  ? (evt.attachments as MessageAttachment[])
                  : m.attachments,
                streaming: false,
              }
            }),
          }))
        },

        onBusinessError: (evt) => {
          const submitError: SubmitMessageError =
            evt.code === ERR_CHAT_SERVICE
              ? { kind: 'service_error', message: evt.message }
              : evt.code === ERR_CHAT_QUOTA_EXHAUSTED
                ? { kind: 'quota_exhausted' }
                : evt.code === ERR_RATE_LIMIT
                  ? { kind: 'rate_limit' }
                  : evt.code === ERR_CONTENT_VIOLATION
                    ? { kind: 'content_violation', message: evt.message }
                    : { kind: 'service_error', message: evt.message }
          // 内容违规走"未消耗"路径：bubble 已被回滚（finish 自身或 page 处理）
          if (submitError.kind !== 'content_violation') {
            markStreamingBubbleErrored('生成中断，请重试')
          }
          finish(wrapError(evt.message, submitError))
        },

        onTransportError: (err, meta) => {
          if (meta.aborted) {
            markStreamingBubbleErrored('已中断')
            finish(
              wrapError(err.message, { kind: 'network', message: err.message }, err),
            )
            return
          }
          recoverFromHistory().then((recovered) => {
            if (recovered) {
              finish()
            } else {
              markStreamingBubbleErrored('网络中断')
              finish(
                wrapError(err.message, {
                  kind: 'network',
                  message: err.message,
                }, err),
              )
            }
          })
        },

        onClose: () => {
          if (!sawAnyEvent) {
            recoverFromHistory().then((recovered) => {
              if (!recovered) markStreamingBubbleErrored('生成中断，请重试')
              finish()
            })
            return
          }
          finish()
        },
      },
    )

    set({ activeStream: cancel })
  })
}
