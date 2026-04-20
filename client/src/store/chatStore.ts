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
import { chatService } from '@/services/chatService'
import type { StreamCancel } from '@/utils/sseClient'
import type {
  DisplayChatMessage,
  MessageAttachment,
  QuickQuestionItem,
} from '@/types/chat'
import type { UserQuota } from '@/types/api'

/** 业务错误码（对齐 docs/02） */
const ERR_CHAT_QUOTA_EXHAUSTED = 40007
const ERR_RATE_LIMIT = 40009
const ERR_CHAT_SERVICE = 50106

export type ChatQuotaSnapshot = {
  /** -1 = 会员无限；0..N = 剩余轮次 */
  remaining: number
  total: number
}

export type SubmitMessageError =
  | { kind: 'quota_exhausted' }
  | { kind: 'rate_limit' }
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
      const msg = err instanceof Error ? err.message : '加载对话失败'
      set({ loading: false, bootstrapError: msg })
      throw err
    }
  },

  /* ============================== 流式发送 ============================== */
  submitMessage(content) {
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
            // 用服务端 id 替换占位，content 暂时还是 user 的原文（后端也返回了）
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
            set((state) => ({
              messages: state.messages.map((m, idx) =>
                idx === state.messages.length - 1 && m.role === 'assistant'
                  ? { ...m, content: m.content + evt.delta }
                  : m,
              ),
            }))
          },

          onAttachment: (evt) => {
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
            // 后端已退配额；assistant 气泡保留（若有部分内容）但标记 errored
            const submitError: SubmitMessageError =
              evt.code === ERR_CHAT_SERVICE
                ? { kind: 'service_error', message: evt.message }
                : evt.code === ERR_CHAT_QUOTA_EXHAUSTED
                  ? { kind: 'quota_exhausted' }
                  : evt.code === ERR_RATE_LIMIT
                    ? { kind: 'rate_limit' }
                    : { kind: 'service_error', message: evt.message }

            set((state) => ({
              messages: state.messages.map((m, idx) => {
                if (idx !== state.messages.length - 1) return m
                if (m.role !== 'assistant') return m
                return {
                  ...m,
                  content: m.content || '生成中断，请重试',
                  streaming: false,
                  errored: true,
                }
              }),
            }))
            finish(wrapError(evt.message, submitError))
          },

          onTransportError: (err, meta) => {
            // 传输层：无法确定后端是否落库/退配额。保守做法：
            //  - 保留用户消息（用户总觉得自己"发出去了"，如果后端没落，下轮 bootstrap 会对齐）
            //  - assistant 占位改为 errored（显示"点击重试"）
            set((state) => ({
              messages: state.messages.map((m, idx) => {
                if (idx !== state.messages.length - 1) return m
                if (m.role !== 'assistant') return m
                return {
                  ...m,
                  content: m.content || (meta.aborted ? '已中断' : '网络中断'),
                  streaming: false,
                  errored: true,
                }
              }),
            }))
            finish(wrapError(err.message, {
              kind: 'network',
              message: err.message,
            }))
          },

          onClose: () => {
            finish()
          },
        },
      )

      set({ activeStream: cancel })
    })
  },

  /* ============================== 非流式（兜底 / 测试） ============================== */
  async submitMessageSync(content) {
    const text = content.trim()
    if (!text) return
    const { currentSessionId, sending } = get()
    if (!currentSessionId) throw new Error('会话未就绪，请稍后再试')
    if (sending) return

    set({ sending: true })
    const pendingId = localId('msg-user')
    const pending: DisplayChatMessage = {
      id: pendingId,
      role: 'user',
      content: text,
      attachments: [],
      created_at: new Date().toISOString(),
      pending: true,
    }
    set({ messages: [...get().messages, pending] })

    try {
      const resp = await chatService.sendMessage(currentSessionId, {
        content: text,
      })
      set((state) => ({
        messages: [
          ...state.messages.filter((m) => m.id !== pendingId),
          resp.user_message as DisplayChatMessage,
          resp.assistant_message as DisplayChatMessage,
        ],
        quota: { ...state.quota, remaining: resp.quota_remaining },
        sending: false,
      }))
    } catch (err) {
      set((state) => ({
        messages: state.messages.filter((m) => m.id !== pendingId),
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
function mapSubmitError(err: unknown): Error & { submitError: SubmitMessageError } {
  const message = err instanceof Error ? err.message : '网络异常'
  const code = (err as { code?: number }).code
  let submitError: SubmitMessageError
  if (code === ERR_CHAT_QUOTA_EXHAUSTED) {
    submitError = { kind: 'quota_exhausted' }
  } else if (code === ERR_RATE_LIMIT) {
    submitError = { kind: 'rate_limit' }
  } else if (code === ERR_CHAT_SERVICE) {
    submitError = { kind: 'service_error', message }
  } else {
    submitError = { kind: 'network', message }
  }
  return wrapError(message, submitError)
}

function wrapError(
  message: string,
  submitError: SubmitMessageError,
): Error & { submitError: SubmitMessageError } {
  const wrapped = new Error(message) as Error & { submitError: SubmitMessageError }
  wrapped.submitError = submitError
  return wrapped
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
  SERVICE_ERROR: ERR_CHAT_SERVICE,
} as const
