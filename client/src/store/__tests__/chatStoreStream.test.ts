/**
 * chatStore.submitMessage（流式）单测
 *
 * 测试策略：mock 出 `chatService.streamMessage` 的 handlers 接口，让测试控制
 * 何时触发 onStart / onDelta / onEnd / onBusinessError / onTransportError / onClose，
 * 然后断言 store state 变化（messages / sending / quota / activeStream / pending）。
 *
 * 我们不再去测 sseClient 那一层（D2a 已锁），这里只验**编排**层不变式：
 *   1. 乐观插入 user + assistant streaming 占位
 *   2. onStart 把 pending=false + 服务端 id 替换
 *   3. onDelta 追加到最后 assistant content
 *   4. onAttachment 追加到最后 assistant attachments
 *   5. onEnd 更新 quota + streaming=false + 最终 content/attachments
 *   6. onBusinessError quota_exhausted → markStreamingBubbleErrored（assistant 气泡 errored）
 *   7. onBusinessError content_violation → 不 mark errored（外层 page 处理）
 *   8. onTransportError aborted → markStreamingBubbleErrored "已中断"
 *   9. onTransportError 非 abort + history 拿不到 → "网络中断" 兜底
 *  10. onClose 且 sawAnyEvent=false → recoverFromHistory → 拿到上一条 assistant 时
 *      替换最后一条占位为后端版本（不报错）
 *  11. 输入校验：空 / 长度 > 500 / sending 中
 *  12. cancelActiveStream / reset 时调用 cancel
 */

import {
  CHAT_ERROR_CODES,
  chatErrorCause,
  getSubmitError,
  useChatStore,
} from '@/store/chatStore'
import { chatService } from '@/services/chatService'
import type {
  StreamStartEvent,
  StreamDeltaEvent,
  StreamEndEvent,
  StreamErrorEvent,
  StreamHandlers,
} from '@/services/chatService'

// ============================================================================
// helpers
// ============================================================================

type Capture = {
  handlers?: StreamHandlers
  cancel: jest.Mock
}

function captureStreamMessage(): Capture {
  const cap: Capture = { cancel: jest.fn() }
  jest.spyOn(chatService, 'streamMessage').mockImplementation((_sid, _body, h) => {
    cap.handlers = h
    return cap.cancel
  })
  return cap
}

function freshStore(sessionId: string | null = 'sess-1'): void {
  useChatStore.setState({
    currentSessionId: sessionId,
    contextAnalysisId: null,
    messages: [],
    quickQuestions: [],
    quota: { remaining: 5, total: 10 },
    loading: false,
    sending: false,
    bootstrapError: null,
    activeStream: null,
  })
}

function lastAssistant() {
  const msgs = useChatStore.getState().messages
  return [...msgs].reverse().find((m) => m.role === 'assistant')
}

// chatStore.submitMessage 在 TARO_ENV=weapp 且 weappSupportsChunkedStreaming() 为 true
// 时才走流式实现；后者读 wx.canIUse('request.object.enableChunked')。
// jest.polyfills.cjs 默认 TARO_ENV=weapp，这里 stub 一个 wx 让它返回 true。
beforeAll(() => {
  ;(globalThis as unknown as { wx: { canIUse: jest.Mock } }).wx = {
    canIUse: jest.fn().mockReturnValue(true),
  }
})
afterAll(() => {
  delete (globalThis as unknown as { wx?: unknown }).wx
})

beforeEach(() => {
  freshStore()
  jest.restoreAllMocks()
})

// ============================================================================
// 输入校验
// ============================================================================

describe('chatStore.submitMessage · 输入校验', () => {
  test('空消息 → 不发起任何 SSE', async () => {
    const spy = jest.spyOn(chatService, 'streamMessage')
    await useChatStore.getState().submitMessage('   ')
    expect(spy).not.toHaveBeenCalled()
    expect(useChatStore.getState().messages).toEqual([])
  })

  test('超过 500 字 → reject "单条消息最多 500 字"', async () => {
    const spy = jest.spyOn(chatService, 'streamMessage')
    await expect(
      useChatStore.getState().submitMessage('a'.repeat(501)),
    ).rejects.toThrow('单条消息最多 500 字')
    expect(spy).not.toHaveBeenCalled()
  })

  test('无 session → reject "会话未就绪"', async () => {
    freshStore(null)
    const spy = jest.spyOn(chatService, 'streamMessage')
    await expect(useChatStore.getState().submitMessage('hi')).rejects.toThrow('会话未就绪')
    expect(spy).not.toHaveBeenCalled()
  })

  test('sending=true 时再次提交直接 no-op', async () => {
    useChatStore.setState({ sending: true })
    const spy = jest.spyOn(chatService, 'streamMessage')
    await useChatStore.getState().submitMessage('hi')
    expect(spy).not.toHaveBeenCalled()
  })
})

// ============================================================================
// 乐观插入
// ============================================================================

describe('chatStore.submitMessage · 乐观插入', () => {
  test('调用后立刻插入 pending user + assistant streaming 占位', () => {
    const cap = captureStreamMessage()
    void useChatStore.getState().submitMessage('hi')
    const msgs = useChatStore.getState().messages
    expect(msgs).toHaveLength(2)
    expect(msgs[0]).toMatchObject({ role: 'user', content: 'hi', pending: true })
    expect(msgs[1]).toMatchObject({
      role: 'assistant',
      content: '',
      streaming: true,
      pending: true,
    })
    expect(useChatStore.getState().sending).toBe(true)
    expect(useChatStore.getState().activeStream).toBe(cap.cancel)
  })
})

// ============================================================================
// 事件流：正常路径
// ============================================================================

describe('chatStore.submitMessage · 正常事件流', () => {
  test('onStart → 替换两条占位的 id，pending=false', async () => {
    const cap = captureStreamMessage()
    const promise = useChatStore.getState().submitMessage('hi')

    cap.handlers!.onStart({
      user_message_id: 'srv-u-1',
      assistant_message_id: 'srv-a-1',
      user_message: {
        id: 'srv-u-1',
        role: 'user',
        content: 'hi',
        created_at: '2026-01-01',
        attachments: [],
      },
    } as StreamStartEvent)

    const msgs = useChatStore.getState().messages
    expect(msgs[0].id).toBe('srv-u-1')
    expect(msgs[0].pending).toBe(false)
    expect(msgs[1].id).toBe('srv-a-1')
    expect(msgs[1].pending).toBe(false)
    expect(msgs[1].streaming).toBe(true)

    cap.handlers!.onEnd({
      assistant_message_id: 'srv-a-1',
      content: 'final',
      attachments: [],
      quota_remaining: 4,
    } as StreamEndEvent)
    cap.handlers!.onClose?.()
    await promise
  })

  test('onDelta 多次累加到 assistant.content', async () => {
    const cap = captureStreamMessage()
    const promise = useChatStore.getState().submitMessage('hi')
    cap.handlers!.onStart({
      user_message_id: 'u',
      assistant_message_id: 'a',
      user_message: {
        id: 'u',
        role: 'user',
        content: 'hi',
        created_at: '',
        attachments: [],
      },
    } as StreamStartEvent)
    cap.handlers!.onDelta({ delta: 'hel' } as StreamDeltaEvent)
    cap.handlers!.onDelta({ delta: 'lo' } as StreamDeltaEvent)
    cap.handlers!.onDelta({ delta: ' 世界' } as StreamDeltaEvent)

    expect(lastAssistant()?.content).toBe('hello 世界')

    cap.handlers!.onEnd({
      assistant_message_id: 'a',
      content: 'hello 世界',
      attachments: [],
      quota_remaining: 4,
    } as StreamEndEvent)
    cap.handlers!.onClose?.()
    await promise
  })

  test('onAttachment 追加到 assistant.attachments', async () => {
    const cap = captureStreamMessage()
    const promise = useChatStore.getState().submitMessage('hi')
    cap.handlers!.onStart({
      user_message_id: 'u',
      assistant_message_id: 'a',
      user_message: {
        id: 'u',
        role: 'user',
        content: 'hi',
        created_at: '',
        attachments: [],
      },
    } as StreamStartEvent)
    cap.handlers!.onAttachment({
      attachment: { type: 'analysis_report', id: 'r1', title: '' },
    } as Parameters<NonNullable<StreamHandlers['onAttachment']>>[0])
    cap.handlers!.onAttachment({
      attachment: { type: 'drill_card', id: 'd1', title: '' },
    } as Parameters<NonNullable<StreamHandlers['onAttachment']>>[0])

    expect(lastAssistant()?.attachments).toHaveLength(2)
    expect(lastAssistant()?.attachments[0]).toMatchObject({ type: 'analysis_report' })

    cap.handlers!.onEnd({
      assistant_message_id: 'a',
      content: '',
      attachments: [],
      quota_remaining: 4,
    } as StreamEndEvent)
    cap.handlers!.onClose?.()
    await promise
  })

  test('onEnd 更新 quota.remaining + assistant.streaming=false', async () => {
    const cap = captureStreamMessage()
    const promise = useChatStore.getState().submitMessage('hi')
    cap.handlers!.onStart({
      user_message_id: 'u',
      assistant_message_id: 'a',
      user_message: {
        id: 'u',
        role: 'user',
        content: 'hi',
        created_at: '',
        attachments: [],
      },
    } as StreamStartEvent)
    cap.handlers!.onEnd({
      assistant_message_id: 'srv-a',
      content: 'all done',
      attachments: [],
      quota_remaining: 2,
    } as StreamEndEvent)
    cap.handlers!.onClose?.()
    await promise

    const state = useChatStore.getState()
    expect(state.quota.remaining).toBe(2)
    expect(state.quota.total).toBe(10) // total 保留不变
    expect(lastAssistant()?.streaming).toBe(false)
    expect(lastAssistant()?.id).toBe('srv-a')
    expect(lastAssistant()?.content).toBe('all done')
    expect(state.sending).toBe(false)
    expect(state.activeStream).toBeNull()
  })
})

// ============================================================================
// 业务错误事件
// ============================================================================

describe('chatStore.submitMessage · 业务错误事件 (event: error)', () => {
  test('quota_exhausted → assistant 气泡 errored，user 气泡保留（后端已落库）', async () => {
    const cap = captureStreamMessage()
    const promise = useChatStore.getState().submitMessage('hi')

    cap.handlers!.onBusinessError({
      code: CHAT_ERROR_CODES.QUOTA_EXHAUSTED,
      message: '配额已耗尽',
    } as StreamErrorEvent)

    await expect(promise).rejects.toThrow('配额已耗尽')

    // user 气泡保留（仍然两条）
    const msgs = useChatStore.getState().messages
    expect(msgs).toHaveLength(2)
    expect(msgs[0].role).toBe('user')
    // assistant 标记 errored、不再 streaming
    expect(msgs[1].errored).toBe(true)
    expect(msgs[1].streaming).toBe(false)
  })

  test('content_violation → 不 mark errored（外层 page 处理回滚）', async () => {
    const cap = captureStreamMessage()
    const promise = useChatStore.getState().submitMessage('hi')

    cap.handlers!.onBusinessError({
      code: CHAT_ERROR_CODES.CONTENT_VIOLATION,
      message: '请修改后再发',
    } as StreamErrorEvent)

    await expect(promise).rejects.toMatchObject({ message: '请修改后再发' })
    const err = await promise.catch((e) => e)
    expect(getSubmitError(err)).toEqual({
      kind: 'content_violation',
      message: '请修改后再发',
    })

    // assistant 气泡不 errored，仍 streaming=true
    expect(lastAssistant()?.errored).toBeUndefined()
  })

  test('rate_limit → mapped 到 rate_limit kind 且 errored', async () => {
    const cap = captureStreamMessage()
    const promise = useChatStore.getState().submitMessage('hi')
    cap.handlers!.onBusinessError({
      code: CHAT_ERROR_CODES.RATE_LIMIT,
      message: '太快了',
    } as StreamErrorEvent)

    const err = await promise.catch((e) => e)
    expect(getSubmitError(err)).toEqual({ kind: 'rate_limit' })
    expect(lastAssistant()?.errored).toBe(true)
  })

  test('service_error / 未知码 → service_error kind', async () => {
    const cap = captureStreamMessage()
    const promise = useChatStore.getState().submitMessage('hi')
    cap.handlers!.onBusinessError({
      code: CHAT_ERROR_CODES.SERVICE_ERROR,
      message: '上游 LLM 不可用',
    } as StreamErrorEvent)

    const err = await promise.catch((e) => e)
    expect(getSubmitError(err)).toEqual({
      kind: 'service_error',
      message: '上游 LLM 不可用',
    })
  })
})

// ============================================================================
// 传输层错误
// ============================================================================

describe('chatStore.submitMessage · 传输层错误', () => {
  test('aborted=true（用户取消）→ markStreamingBubbleErrored "已中断"', async () => {
    const cap = captureStreamMessage()
    const promise = useChatStore.getState().submitMessage('hi')

    cap.handlers!.onTransportError(new Error('连接已中断'), { aborted: true })

    const err = await promise.catch((e) => e)
    expect(getSubmitError(err)).toMatchObject({ kind: 'network' })
    expect(lastAssistant()?.content).toBe('已中断')
    expect(lastAssistant()?.errored).toBe(true)
    expect(chatErrorCause(err)).toBeInstanceOf(Error)
  })

  test('aborted=false + history 无 assistant → "网络中断" 兜底', async () => {
    jest.spyOn(chatService, 'getMessages').mockResolvedValue({
      items: [],
      next_page: null,
    } as Awaited<ReturnType<typeof chatService.getMessages>>)
    const cap = captureStreamMessage()
    const promise = useChatStore.getState().submitMessage('hi')

    cap.handlers!.onTransportError(new Error('TLS 失败'), { aborted: false })

    await expect(promise).rejects.toThrow('TLS 失败')
    expect(lastAssistant()?.content).toBe('网络中断')
    expect(lastAssistant()?.errored).toBe(true)
  })

  test('aborted=false + history 有 assistant → 替换占位 + resolve 不报错', async () => {
    jest.spyOn(chatService, 'getMessages').mockResolvedValue({
      items: [
        {
          id: 'srv-u',
          role: 'user',
          content: 'hi',
          created_at: '',
          attachments: [],
        },
        {
          id: 'srv-a',
          role: 'assistant',
          content: '答案来自历史回放',
          created_at: '',
          attachments: [],
        },
      ],
      next_page: null,
    } as Awaited<ReturnType<typeof chatService.getMessages>>)
    const cap = captureStreamMessage()
    const promise = useChatStore.getState().submitMessage('hi')

    cap.handlers!.onTransportError(new Error('卡顿一下'), { aborted: false })

    await promise // 不抛错
    expect(lastAssistant()?.id).toBe('srv-a')
    expect(lastAssistant()?.content).toBe('答案来自历史回放')
    expect(lastAssistant()?.streaming).toBe(false)
    expect(lastAssistant()?.errored).toBeUndefined()
  })
})

// ============================================================================
// onClose 兜底 / cancel
// ============================================================================

describe('chatStore.submitMessage · onClose 兜底 & cancel', () => {
  test('onClose 在没有任何事件前到达（sawAnyEvent=false）→ recoverFromHistory；拿到 → 静默 resolve', async () => {
    jest.spyOn(chatService, 'getMessages').mockResolvedValue({
      items: [
        {
          id: 'srv-a',
          role: 'assistant',
          content: '保底回放',
          created_at: '',
          attachments: [],
        },
      ],
      next_page: null,
    } as Awaited<ReturnType<typeof chatService.getMessages>>)
    const cap = captureStreamMessage()
    const promise = useChatStore.getState().submitMessage('hi')

    cap.handlers!.onClose?.()

    await promise
    expect(lastAssistant()?.content).toBe('保底回放')
  })

  test('cancelActiveStream() 调用 activeStream cancel + 清空 sending', () => {
    const cap = captureStreamMessage()
    void useChatStore.getState().submitMessage('hi')
    expect(useChatStore.getState().activeStream).toBe(cap.cancel)

    useChatStore.getState().cancelActiveStream()
    expect(cap.cancel).toHaveBeenCalledTimes(1)
    expect(useChatStore.getState().activeStream).toBeNull()
    expect(useChatStore.getState().sending).toBe(false)
  })

  test('reset() 也会 abort 活跃 stream', () => {
    const cap = captureStreamMessage()
    void useChatStore.getState().submitMessage('hi')
    useChatStore.getState().reset()
    expect(cap.cancel).toHaveBeenCalled()
    expect(useChatStore.getState().messages).toEqual([])
    expect(useChatStore.getState().currentSessionId).toBeNull()
  })
})
