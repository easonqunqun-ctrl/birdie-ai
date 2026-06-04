/**
 * chatStore.ts 单测：bootstrap / submitMessageSync 乐观更新 / 错误映射 / reset
 *
 * 流式编排（submitMessage / submitMessageStreamImpl）涉及 SSE 状态机，
 * 测试代价大；首批只覆盖 W3.x 兜底必经的非流式分支。
 */

import { RequestError } from '@/services/request'

// Mock chatService（必须在 chatStore import 前）
jest.mock('@/services/chatService', () => ({
  chatService: {
    getQuickQuestions: jest.fn(),
    createSession: jest.fn(),
    getMessages: jest.fn(),
    sendMessage: jest.fn(),
    deleteSession: jest.fn(),
    listSessions: jest.fn(),
    streamMessage: jest.fn(),
  },
}))
jest.mock('@/utils/sseClient', () => ({
  weappSupportsChunkedStreaming: jest.fn(() => false),
  streamSSE: jest.fn(),
}))

import {
  useChatStore,
  CHAT_ERROR_CODES,
  getSubmitError,
  chatErrorCause,
} from '@/store/chatStore'
import { chatService } from '@/services/chatService'

const mocked = {
  getQuickQuestions: chatService.getQuickQuestions as jest.Mock,
  createSession: chatService.createSession as jest.Mock,
  getMessages: chatService.getMessages as jest.Mock,
  sendMessage: chatService.sendMessage as jest.Mock,
  deleteSession: chatService.deleteSession as jest.Mock,
}

function reset() {
  useChatStore.setState({
    currentSessionId: null,
    contextAnalysisId: null,
    messages: [],
    quickQuestions: [],
    quota: { remaining: -1, total: -1 },
    loading: false,
    sending: false,
    bootstrapError: null,
    activeStream: null,
  })
}

beforeEach(() => {
  reset()
  Object.values(mocked).forEach((m) => m.mockReset())
})

describe('useChatStore.hydrateQuotaFromUser', () => {
  test('userQuota=null → no-op', () => {
    useChatStore.getState().hydrateQuotaFromUser(null)
    expect(useChatStore.getState().quota).toEqual({ remaining: -1, total: -1 })
  })

  test('userQuota → 写入 remaining/total', () => {
    useChatStore.getState().hydrateQuotaFromUser({
      chat_remaining_today: 8,
      chat_total_today: 10,
    } as any)
    expect(useChatStore.getState().quota).toEqual({ remaining: 8, total: 10 })
  })
})

describe('useChatStore.loadGuestPreview', () => {
  test('成功 → 仅填充 quickQuestions，不创建 session', async () => {
    mocked.getQuickQuestions.mockResolvedValue({
      questions: [{ id: 'q1', text: 'test', requires_analysis: false }],
    })
    await useChatStore.getState().loadGuestPreview()
    const s = useChatStore.getState()
    expect(s.quickQuestions).toHaveLength(1)
    expect(s.currentSessionId).toBeNull()
    expect(s.loading).toBe(false)
    expect(mocked.createSession).not.toHaveBeenCalled()
  })

  test('失败 → 不写入 bootstrapError', async () => {
    mocked.getQuickQuestions.mockRejectedValue(new Error('network'))
    await useChatStore.getState().loadGuestPreview()
    const s = useChatStore.getState()
    expect(s.quickQuestions).toEqual([])
    expect(s.bootstrapError).toBeNull()
    expect(s.loading).toBe(false)
  })
})

describe('useChatStore.bootstrapSession', () => {
  test('成功 → 同时填充 session + quickQuestions', async () => {
    mocked.getQuickQuestions.mockResolvedValue({ questions: [{ id: 'q1' }] })
    mocked.createSession.mockResolvedValue({
      session_id: 's1',
      context_analysis_id: 'a1',
      messages: [],
    })

    await useChatStore.getState().bootstrapSession('a1')

    const s = useChatStore.getState()
    expect(s.currentSessionId).toBe('s1')
    expect(s.contextAnalysisId).toBe('a1')
    expect(s.quickQuestions).toEqual([{ id: 'q1' }])
    expect(s.loading).toBe(false)
    expect(s.bootstrapError).toBeNull()
    expect(mocked.createSession).toHaveBeenCalledWith({ context_analysis_id: 'a1' })
  })

  test('contextAnalysisId 未传 → createSession 用 {}', async () => {
    mocked.getQuickQuestions.mockResolvedValue({ questions: [] })
    mocked.createSession.mockResolvedValue({
      session_id: 's',
      context_analysis_id: null,
      messages: [],
    })
    await useChatStore.getState().bootstrapSession()
    expect(mocked.createSession).toHaveBeenCalledWith({})
  })

  test('失败 → bootstrapError 走 describePageLoadFailure，再抛', async () => {
    mocked.getQuickQuestions.mockResolvedValue({ questions: [] })
    mocked.createSession.mockRejectedValue(
      new RequestError('http_server_error', 'HTTP 502', { status: 502 }),
    )

    await expect(
      useChatStore.getState().bootstrapSession('a1'),
    ).rejects.toBeInstanceOf(RequestError)

    const s = useChatStore.getState()
    expect(s.loading).toBe(false)
    expect(s.bootstrapError).toBeTruthy()
    expect(s.bootstrapError).not.toContain('暂停自动刷新') // describePageLoadFailure 去尾缀
  })
})

describe('useChatStore.bootstrapExistingSession', () => {
  test('成功 → 加载现有消息（带 attachments 兜底 []）', async () => {
    mocked.getQuickQuestions.mockResolvedValue({ questions: [] })
    mocked.getMessages.mockResolvedValue({
      items: [{ id: 'm1', role: 'user', content: 'hi' }],
    })
    await useChatStore.getState().bootstrapExistingSession('s1', 'a1')
    const s = useChatStore.getState()
    expect(s.currentSessionId).toBe('s1')
    expect(s.contextAnalysisId).toBe('a1')
    expect(s.messages).toEqual([
      { id: 'm1', role: 'user', content: 'hi', attachments: [] },
    ])
  })

  test('contextAnalysisId undefined → 默认 null', async () => {
    mocked.getQuickQuestions.mockResolvedValue({ questions: [] })
    mocked.getMessages.mockResolvedValue({ items: [] })
    await useChatStore.getState().bootstrapExistingSession('s1')
    expect(useChatStore.getState().contextAnalysisId).toBeNull()
  })
})

describe('useChatStore.submitMessageSync', () => {
  beforeEach(() => {
    useChatStore.setState({ currentSessionId: 's1' })
  })

  test('空文本 → 不发请求', async () => {
    await useChatStore.getState().submitMessageSync('   ')
    expect(mocked.sendMessage).not.toHaveBeenCalled()
  })

  test('超长文本（>500）→ 抛错', async () => {
    await expect(
      useChatStore.getState().submitMessageSync('a'.repeat(501)),
    ).rejects.toThrow('最多 500 字')
  })

  test('未就绪 sessionId → 抛错', async () => {
    useChatStore.setState({ currentSessionId: null })
    await expect(useChatStore.getState().submitMessageSync('hi')).rejects.toThrow(
      '会话未就绪',
    )
  })

  test('sending=true → 跳过本次（防双击）', async () => {
    useChatStore.setState({ sending: true })
    await useChatStore.getState().submitMessageSync('hi')
    expect(mocked.sendMessage).not.toHaveBeenCalled()
  })

  test('成功 → 占位消息被服务端真实消息替换', async () => {
    mocked.sendMessage.mockResolvedValue({
      user_message: { id: 'u1', role: 'user', content: 'hi' },
      assistant_message: { id: 'a1', role: 'assistant', content: 'hello' },
      quota_remaining: 7,
    })

    await useChatStore.getState().submitMessageSync('hi')

    const s = useChatStore.getState()
    expect(s.messages.map((m) => m.id)).toEqual(['u1', 'a1'])
    expect(s.quota.remaining).toBe(7)
    expect(s.sending).toBe(false)
  })

  test('quota_exhausted (40007) → 回滚占位 + submitError.kind=quota_exhausted', async () => {
    mocked.sendMessage.mockRejectedValue(
      new RequestError('business', '本日配额已用完', {
        code: CHAT_ERROR_CODES.QUOTA_EXHAUSTED,
      }),
    )

    let caught: unknown
    try {
      await useChatStore.getState().submitMessageSync('hi')
    } catch (e) {
      caught = e
    }
    expect(getSubmitError(caught)).toEqual({ kind: 'quota_exhausted' })
    expect(chatErrorCause(caught)).toBeInstanceOf(RequestError)

    const s = useChatStore.getState()
    expect(s.messages).toEqual([]) // user + assistant 占位都回滚
    expect(s.sending).toBe(false)
  })

  test('rate_limit (40009) → submitError.kind=rate_limit', async () => {
    mocked.sendMessage.mockRejectedValue(
      new RequestError('business', '太频繁了', { code: CHAT_ERROR_CODES.RATE_LIMIT }),
    )
    let caught: unknown
    try {
      await useChatStore.getState().submitMessageSync('hi')
    } catch (e) {
      caught = e
    }
    expect(getSubmitError(caught)).toEqual({ kind: 'rate_limit' })
  })

  test('content_violation (40017) → 携带 message', async () => {
    mocked.sendMessage.mockRejectedValue(
      new RequestError('business', '内容存在违规', {
        code: CHAT_ERROR_CODES.CONTENT_VIOLATION,
      }),
    )
    let caught: unknown
    try {
      await useChatStore.getState().submitMessageSync('hi')
    } catch (e) {
      caught = e
    }
    expect(getSubmitError(caught)).toEqual({
      kind: 'content_violation',
      message: '内容存在违规',
    })
  })

  test('service_error (50106) → submitError.kind=service_error', async () => {
    mocked.sendMessage.mockRejectedValue(
      new RequestError('business', 'AI 引擎暂时不可用', {
        code: CHAT_ERROR_CODES.SERVICE_ERROR,
      }),
    )
    let caught: unknown
    try {
      await useChatStore.getState().submitMessageSync('hi')
    } catch (e) {
      caught = e
    }
    expect(getSubmitError(caught)?.kind).toBe('service_error')
  })

  test('未知 error → submitError.kind=network', async () => {
    mocked.sendMessage.mockRejectedValue(new Error('boom'))
    let caught: unknown
    try {
      await useChatStore.getState().submitMessageSync('hi')
    } catch (e) {
      caught = e
    }
    expect(getSubmitError(caught)?.kind).toBe('network')
  })
})

describe('useChatStore.clearSession / reset / cancelActiveStream', () => {
  test('clearSession 调 deleteSession 后清状态', async () => {
    useChatStore.setState({ currentSessionId: 's1', messages: [{ id: 'm' } as any] })
    mocked.deleteSession.mockResolvedValue(null)
    await useChatStore.getState().clearSession()
    expect(mocked.deleteSession).toHaveBeenCalledWith('s1')
    const s = useChatStore.getState()
    expect(s.currentSessionId).toBeNull()
    expect(s.messages).toEqual([])
  })

  test('clearSession 即使 deleteSession 失败也要清状态（finally）', async () => {
    useChatStore.setState({ currentSessionId: 's1' })
    mocked.deleteSession.mockRejectedValue(new Error('boom'))
    await expect(useChatStore.getState().clearSession()).rejects.toThrow('boom')
    expect(useChatStore.getState().currentSessionId).toBeNull()
  })

  test('cancelActiveStream 调用 activeStream() 后清掉', () => {
    const fn = jest.fn()
    useChatStore.setState({ activeStream: fn, sending: true })
    useChatStore.getState().cancelActiveStream()
    expect(fn).toHaveBeenCalledTimes(1)
    expect(useChatStore.getState().activeStream).toBeNull()
    expect(useChatStore.getState().sending).toBe(false)
  })

  test('reset 把所有字段恢复初始值', () => {
    useChatStore.setState({
      currentSessionId: 's1',
      messages: [{ id: 'm' } as any],
      sending: true,
      bootstrapError: 'oops',
    })
    useChatStore.getState().reset()
    const s = useChatStore.getState()
    expect(s.currentSessionId).toBeNull()
    expect(s.messages).toEqual([])
    expect(s.sending).toBe(false)
    expect(s.bootstrapError).toBeNull()
  })
})
