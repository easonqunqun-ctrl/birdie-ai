/**
 * @jest-environment node
 *
 * sseClient 单测
 *
 * 改用 node 环境而非默认 jsdom：
 *  - 测试需要 web 标准 `Response` / `ReadableStream` / `fetch`，node 18+ 自带（undici）
 *  - jsdom 默认未提供 Response stream body，强行 polyfill 会跑偏
 *  - sseClient 内部本身不依赖任何 DOM API，跑 node 完全没问题
 *
 * 测试范围：
 *  - streamSSE 端分叉（process.env.TARO_ENV）
 *  - weappSupportsChunkedStreaming：wx.canIUse 真值断言
 *  - H5 路径（fetch + ReadableStream）：协议解析、错误、cancel、超时
 *  - 小程序路径（Taro.request enableChunked + onChunkReceived）：chunk 拼接 /
 *    success 兜底（无 chunk 一次性给 body）/ HTTP 4xx → onError / abort
 *  - SSE 解析协议（通过 H5 路径间接覆盖 SSEParser / parseBlock）：
 *      默认 event=message、event/data 行、非 JSON data 原样、注释行跳过、
 *      跨 chunk 拼接、末尾无 \n\n 时 flush 兜底
 *
 * 注意：
 *  - sseClient.ts 内顶层 `declare const API_BASE_URL` → 在 jest.polyfills.cjs
 *    把 globalThis.API_BASE_URL 设成 http://localhost:8000/v1，buildUrl 会用它
 *  - storage 模块在 src/__mocks__/tarojs.ts 用 in-memory Map 替代真实 Storage，
 *    不需要额外桩
 */
import Taro from '@tarojs/taro'

import { storage } from '@/utils/storage'

// ----------------------------------------------------------------------------
// helpers
// ----------------------------------------------------------------------------

function utf8(s: string): Uint8Array {
  return new TextEncoder().encode(s)
}

function utf8Buffer(s: string): ArrayBuffer {
  const u8 = utf8(s)
  const ab = new ArrayBuffer(u8.byteLength)
  new Uint8Array(ab).set(u8)
  return ab
}

/** 用 jsdom 自带 ReadableStream 包出 fetch.Response 风格的对象 */
function makeResponse(opts: {
  ok: boolean
  status: number
  chunks?: Uint8Array[]
  textBody?: string
  noBody?: boolean
}): Response {
  if (opts.noBody) {
    return new Response(null, { status: opts.status, statusText: '' })
  }
  if (opts.chunks && opts.chunks.length > 0) {
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        opts.chunks!.forEach((c) => controller.enqueue(c))
        controller.close()
      },
    })
    return new Response(stream, { status: opts.status })
  }
  return new Response(opts.textBody ?? '', { status: opts.status })
}

const originalFetch = global.fetch
const originalTaroEnv = process.env.TARO_ENV

beforeEach(() => {
  process.env.TARO_ENV = 'h5'
  jest.useRealTimers()
})

afterEach(() => {
  global.fetch = originalFetch
  process.env.TARO_ENV = originalTaroEnv
})

// ----------------------------------------------------------------------------
// streamSSE · 端分叉
// ----------------------------------------------------------------------------

describe('streamSSE · 端分叉', () => {
  test('h5 走 fetch + AbortController（不是 Taro.request）', async () => {
    process.env.TARO_ENV = 'h5'
    const fetchMock = jest.fn().mockResolvedValue(
      makeResponse({
        ok: true,
        status: 200,
        chunks: [utf8('event: ping\ndata: "ok"\n\n')],
      }),
    )
    global.fetch = fetchMock as unknown as typeof global.fetch

    const { streamSSE } = await import('@/utils/sseClient')
    const events: { type: string; data: unknown }[] = []
    await new Promise<void>((resolve) => {
      streamSSE(
        { url: '/chat/sessions/abc/messages/stream', body: { x: 1 } },
        {
          onEvent: (e) => events.push(e),
          onDone: () => resolve(),
          onError: (err) => {
            throw new Error(`unexpected: ${err.message}`)
          },
        },
      )
    })

    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect((Taro as unknown as { request: jest.Mock }).request).not.toHaveBeenCalled()
    expect(events).toEqual([{ type: 'ping', data: 'ok' }])
  })

  test('weapp 走 Taro.request enableChunked（不是 fetch）', async () => {
    process.env.TARO_ENV = 'weapp'

    // wx.canIUse 返回 true 表示基础库支持 chunked
    const wxStub = {
      canIUse: jest.fn().mockReturnValue(true),
    }
    ;(globalThis as unknown as { wx: typeof wxStub }).wx = wxStub

    const fetchMock = jest.fn()
    global.fetch = fetchMock as unknown as typeof global.fetch

    const events: { type: string; data: unknown }[] = []
    let onChunkCb: ((res: { data: ArrayBuffer }) => void) | undefined
    const task = {
      abort: jest.fn(),
      onChunkReceived: jest.fn((cb) => {
        onChunkCb = cb
      }),
    }
    ;(Taro.request as jest.Mock).mockImplementation((cfg) => {
      // 异步推一帧 chunk + success
      queueMicrotask(() => {
        onChunkCb?.({ data: utf8Buffer('event: hello\ndata: "x"\n\n') })
        ;(cfg.success as (r: { statusCode: number; data: string }) => void)({
          statusCode: 200,
          data: '',
        })
      })
      return task
    })

    const { streamSSE } = await import('@/utils/sseClient')
    await new Promise<void>((resolve) => {
      streamSSE(
        { url: '/chat/sessions/x/messages/stream', body: {} },
        {
          onEvent: (e) => events.push(e),
          onDone: () => resolve(),
          onError: (err) => {
            throw new Error(`unexpected: ${err.message}`)
          },
        },
      )
    })

    expect(Taro.request).toHaveBeenCalledTimes(1)
    expect(fetchMock).not.toHaveBeenCalled()
    expect(events).toEqual([{ type: 'hello', data: 'x' }])
    expect((Taro.request as jest.Mock).mock.calls[0][0]).toMatchObject({
      enableChunked: true,
      responseType: 'text',
    })

    delete (globalThis as unknown as { wx?: typeof wxStub }).wx
  })

  test('rn 走 XMLHttpRequest（不是 Taro.request / fetch）', async () => {
    process.env.TARO_ENV = 'rn'
    const fetchMock = jest.fn()
    global.fetch = fetchMock as unknown as typeof global.fetch
    ;(Taro.request as jest.Mock).mockClear()

    type XhrHandler = (() => void) | null
    const events: { type: string; data: unknown }[] = []
    let responseText = ''
    const xhr = {
      responseType: '',
      status: 200,
      get responseText() {
        return responseText
      },
      open: jest.fn(),
      setRequestHeader: jest.fn(),
      send: jest.fn(() => {
        queueMicrotask(() => {
          responseText = 'event: delta\ndata: "hi"\n\n'
          xhr.onprogress?.()
          xhr.onload?.()
        })
      }),
      abort: jest.fn(),
      onprogress: null as XhrHandler,
      onload: null as XhrHandler,
      onerror: null as XhrHandler,
      onabort: null as XhrHandler,
    }
    const XHR = jest.fn(() => xhr) as unknown as typeof XMLHttpRequest
    global.XMLHttpRequest = XHR

    const { streamSSE } = await import('@/utils/sseClient')
    await new Promise<void>((resolve) => {
      streamSSE(
        { url: '/chat/sessions/rn/messages/stream', body: { q: 1 } },
        {
          onEvent: (e) => events.push(e),
          onDone: () => resolve(),
          onError: (err) => {
            throw new Error(`unexpected: ${err.message}`)
          },
        },
      )
    })

    expect(XHR).toHaveBeenCalled()
    expect(fetchMock).not.toHaveBeenCalled()
    expect(Taro.request).not.toHaveBeenCalled()
    expect(events).toEqual([{ type: 'delta', data: 'hi' }])
  })
})

// ----------------------------------------------------------------------------
// weappSupportsChunkedStreaming
// ----------------------------------------------------------------------------

describe('weappSupportsChunkedStreaming', () => {
  test('wx 不存在 → false', async () => {
    delete (globalThis as unknown as { wx?: unknown }).wx
    const { weappSupportsChunkedStreaming } = await import('@/utils/sseClient')
    expect(weappSupportsChunkedStreaming()).toBe(false)
  })

  test('wx.canIUse 返回 true → true', async () => {
    ;(globalThis as unknown as { wx: { canIUse: jest.Mock } }).wx = {
      canIUse: jest.fn((key: string) => key === 'request.object.enableChunked'),
    }
    const { weappSupportsChunkedStreaming } = await import('@/utils/sseClient')
    expect(weappSupportsChunkedStreaming()).toBe(true)
  })

  test('wx.canIUse 返回 false → false', async () => {
    ;(globalThis as unknown as { wx: { canIUse: jest.Mock } }).wx = {
      canIUse: jest.fn().mockReturnValue(false),
    }
    const { weappSupportsChunkedStreaming } = await import('@/utils/sseClient')
    expect(weappSupportsChunkedStreaming()).toBe(false)
    delete (globalThis as unknown as { wx?: unknown }).wx
  })
})

// ----------------------------------------------------------------------------
// H5 路径 · SSE 协议解析（间接覆盖 SSEParser）
// ----------------------------------------------------------------------------

describe('H5 · SSE 协议解析', () => {
  test('单 chunk 多事件、默认 event=message、JSON data 解析', async () => {
    global.fetch = jest.fn().mockResolvedValue(
      makeResponse({
        ok: true,
        status: 200,
        chunks: [
          utf8('event: content_delta\ndata: {"delta":"你好"}\n\ndata: {"text":"末尾默认 message"}\n\n'),
        ],
      }),
    ) as unknown as typeof global.fetch

    const { streamSSE } = await import('@/utils/sseClient')
    const events: { type: string; data: unknown }[] = []
    await new Promise<void>((resolve) => {
      streamSSE({ url: '/x' }, { onEvent: (e) => events.push(e), onDone: () => resolve() })
    })

    expect(events).toEqual([
      { type: 'content_delta', data: { delta: '你好' } },
      { type: 'message', data: { text: '末尾默认 message' } },
    ])
  })

  test('注释行 (:foo) / 空行被跳过', async () => {
    global.fetch = jest.fn().mockResolvedValue(
      makeResponse({
        ok: true,
        status: 200,
        chunks: [
          utf8(': server heartbeat\nevent: keep_alive\n\nevent: tick\ndata: 1\n\n'),
        ],
      }),
    ) as unknown as typeof global.fetch

    const { streamSSE } = await import('@/utils/sseClient')
    const events: { type: string; data: unknown }[] = []
    await new Promise<void>((resolve) => {
      streamSSE({ url: '/x' }, { onEvent: (e) => events.push(e), onDone: () => resolve() })
    })

    // 第 1 个 block 只有 event:keep_alive 没 data → parseBlock 返回 null
    expect(events).toEqual([{ type: 'tick', data: 1 }])
  })

  test('多 chunk 跨 \\n\\n 边界拼接', async () => {
    global.fetch = jest.fn().mockResolvedValue(
      makeResponse({
        ok: true,
        status: 200,
        chunks: [
          utf8('event: content_delta\ndata: '),
          utf8('{"delta":"hel'),
          utf8('lo"}\n\n'),
          utf8('event: done\ndata: {"reason":"end"}\n\n'),
        ],
      }),
    ) as unknown as typeof global.fetch

    const { streamSSE } = await import('@/utils/sseClient')
    const events: { type: string; data: unknown }[] = []
    await new Promise<void>((resolve) => {
      streamSSE({ url: '/x' }, { onEvent: (e) => events.push(e), onDone: () => resolve() })
    })

    expect(events).toEqual([
      { type: 'content_delta', data: { delta: 'hello' } },
      { type: 'done', data: { reason: 'end' } },
    ])
  })

  test('非 JSON data 原样作为字符串', async () => {
    global.fetch = jest.fn().mockResolvedValue(
      makeResponse({
        ok: true,
        status: 200,
        chunks: [utf8('data: not-json-just-text\n\n')],
      }),
    ) as unknown as typeof global.fetch

    const { streamSSE } = await import('@/utils/sseClient')
    const events: { type: string; data: unknown }[] = []
    await new Promise<void>((resolve) => {
      streamSSE({ url: '/x' }, { onEvent: (e) => events.push(e), onDone: () => resolve() })
    })

    expect(events).toEqual([{ type: 'message', data: 'not-json-just-text' }])
  })

  test('末尾无 \\n\\n 时 flush() 兜底产出最后一个事件', async () => {
    global.fetch = jest.fn().mockResolvedValue(
      makeResponse({
        ok: true,
        status: 200,
        // 注意：第二个 event 没有 \n\n 收尾
        chunks: [utf8('event: a\ndata: {"i":1}\n\nevent: b\ndata: {"i":2}')],
      }),
    ) as unknown as typeof global.fetch

    const { streamSSE } = await import('@/utils/sseClient')
    const events: { type: string; data: unknown }[] = []
    await new Promise<void>((resolve) => {
      streamSSE({ url: '/x' }, { onEvent: (e) => events.push(e), onDone: () => resolve() })
    })

    expect(events).toEqual([
      { type: 'a', data: { i: 1 } },
      { type: 'b', data: { i: 2 } },
    ])
  })
})

// ----------------------------------------------------------------------------
// H5 路径 · 错误 / 取消 / 超时 / 鉴权
// ----------------------------------------------------------------------------

describe('H5 · 错误 / 取消 / 鉴权', () => {
  test('HTTP 4xx：onError 带状态码 + 业务 message', async () => {
    global.fetch = jest.fn().mockResolvedValue(
      makeResponse({
        ok: false,
        status: 429,
        textBody: JSON.stringify({ message: '请求过于频繁' }),
      }),
    ) as unknown as typeof global.fetch

    const { streamSSE } = await import('@/utils/sseClient')
    const errors: { msg: string; aborted: boolean }[] = []
    await new Promise<void>((resolve) => {
      streamSSE(
        { url: '/x' },
        {
          onEvent: () => undefined,
          onError: (e, meta) => {
            errors.push({ msg: e.message, aborted: meta.aborted })
            resolve()
          },
        },
      )
    })

    expect(errors).toHaveLength(1)
    expect(errors[0].msg).toBe('HTTP 429：请求过于频繁')
    expect(errors[0].aborted).toBe(false)
  })

  test('res.body 为 null → onError "流式响应无 body"', async () => {
    global.fetch = jest
      .fn()
      .mockResolvedValue(makeResponse({ ok: true, status: 200, noBody: true })) as unknown as typeof global.fetch

    const { streamSSE } = await import('@/utils/sseClient')
    const errors: string[] = []
    await new Promise<void>((resolve) => {
      streamSSE(
        { url: '/x' },
        {
          onEvent: () => undefined,
          onError: (e) => {
            errors.push(e.message)
            resolve()
          },
        },
      )
    })
    expect(errors).toEqual(['流式响应无 body'])
  })

  test('fetch reject → onError 透传 message', async () => {
    global.fetch = jest.fn().mockRejectedValue(new Error('boom')) as unknown as typeof global.fetch
    const { streamSSE } = await import('@/utils/sseClient')
    const errors: string[] = []
    await new Promise<void>((resolve) => {
      streamSSE(
        { url: '/x' },
        {
          onEvent: () => undefined,
          onError: (e) => {
            errors.push(e.message)
            resolve()
          },
        },
      )
    })
    expect(errors).toEqual(['boom'])
  })

  test('调用 cancel() 后 AbortError 被识别成 aborted', async () => {
    // 实现一个永不 resolve 的 fetch，等被 abort
    let abortSignalCaptured: AbortSignal | undefined
    global.fetch = jest.fn((_url, init: RequestInit) => {
      abortSignalCaptured = init.signal as AbortSignal
      return new Promise((_resolve, reject) => {
        abortSignalCaptured?.addEventListener('abort', () => {
          const err = new Error('aborted') as Error & { name: string }
          err.name = 'AbortError'
          reject(err)
        })
      })
    }) as unknown as typeof global.fetch

    const { streamSSE } = await import('@/utils/sseClient')
    const errors: { msg: string; aborted: boolean }[] = []
    const cancel = streamSSE(
      { url: '/x', timeoutMs: 10000 },
      {
        onEvent: () => undefined,
        onError: (e, meta) => errors.push({ msg: e.message, aborted: meta.aborted }),
      },
    )

    // 让 fetch 真的开始等
    await new Promise((r) => setTimeout(r, 5))
    cancel()
    // 等 abort 信号传到 reject、reject 进入 catch
    await new Promise((r) => setTimeout(r, 20))

    // cancel() 自己会 controller.abort() → fetch 抛 AbortError → onError aborted=true
    // 但 streamH5 自己的 cancel callback 把 done=true，理论上 cancel 后的 onError 不再触发；
    // 在 streamH5 实现里：cancel 走 done=true、随后 fetch reject 会 if(done) return。
    // 但若 abort 之前 fetch 已经在执行 try{}，被 abort 后 catch 里 done 仍是 false（因为
    // cancel 前没设 done）—— 实际看源码：cancel 里 `if (!done) { done = true; abort() }`，
    // 然后 reject 进 catch 时 done=true → if(done) return。
    // 即不会再调用 onError。这是预期：cancel 是 "silent" 中断。
    expect(errors).toHaveLength(0)
  })

  test('Bearer Token 自动注入 / noAuth=true 时不注入', async () => {
    storage.setToken('test-token-xyz')
    const calls: RequestInit[] = []
    global.fetch = jest.fn((_url, init: RequestInit) => {
      calls.push(init)
      return Promise.resolve(
        makeResponse({ ok: true, status: 200, chunks: [utf8('data: 1\n\n')] }),
      )
    }) as unknown as typeof global.fetch

    const { streamSSE } = await import('@/utils/sseClient')
    await new Promise<void>((resolve) =>
      streamSSE({ url: '/x' }, { onEvent: () => undefined, onDone: () => resolve() }),
    )
    await new Promise<void>((resolve) =>
      streamSSE({ url: '/x', noAuth: true }, { onEvent: () => undefined, onDone: () => resolve() }),
    )

    expect(calls).toHaveLength(2)
    const h1 = calls[0].headers as Record<string, string>
    const h2 = calls[1].headers as Record<string, string>
    expect(h1.Authorization).toBe('Bearer test-token-xyz')
    expect(h2.Authorization).toBeUndefined()
    storage.clearAuthSession()
  })

  test('buildUrl：以 / 开头时拼 API_BASE_URL；以 http 开头时直接使用', async () => {
    const calls: string[] = []
    global.fetch = jest.fn((url: string) => {
      calls.push(url)
      return Promise.resolve(
        makeResponse({ ok: true, status: 200, chunks: [utf8('data: 1\n\n')] }),
      )
    }) as unknown as typeof global.fetch

    const { streamSSE } = await import('@/utils/sseClient')
    await new Promise<void>((resolve) =>
      streamSSE(
        { url: '/chat/stream' },
        { onEvent: () => undefined, onDone: () => resolve() },
      ),
    )
    await new Promise<void>((resolve) =>
      streamSSE(
        { url: 'http://example.com/x' },
        { onEvent: () => undefined, onDone: () => resolve() },
      ),
    )

    expect(calls[0]).toBe('http://localhost:8000/v1/chat/stream')
    expect(calls[1]).toBe('http://example.com/x')
  })
})

// ----------------------------------------------------------------------------
// 小程序路径 · 关键分支
// ----------------------------------------------------------------------------

describe('weapp · 关键分支', () => {
  beforeEach(() => {
    process.env.TARO_ENV = 'weapp'
    ;(globalThis as unknown as { wx: { canIUse: jest.Mock } }).wx = {
      canIUse: jest.fn().mockReturnValue(true),
    }
  })
  afterEach(() => {
    delete (globalThis as unknown as { wx?: unknown }).wx
  })

  test('基础库不支持 chunked → onError 提示升级微信', async () => {
    ;(globalThis as unknown as { wx: { canIUse: jest.Mock } }).wx = {
      canIUse: jest.fn().mockReturnValue(false),
    }
    const { streamSSE } = await import('@/utils/sseClient')
    const errors: string[] = []
    await new Promise<void>((resolve) => {
      streamSSE(
        { url: '/x' },
        {
          onEvent: () => undefined,
          onError: (e) => {
            errors.push(e.message)
            resolve()
          },
        },
      )
    })
    expect(errors[0]).toMatch(/当前微信版本不支持流式对话/)
    // 没真正发请求
    expect(Taro.request).not.toHaveBeenCalled()
  })

  test('onChunkReceived 一次也没触发时，success 把 res.data 当成整块兜底解析', async () => {
    const task = {
      abort: jest.fn(),
      onChunkReceived: jest.fn(),
    }
    ;(Taro.request as jest.Mock).mockImplementation((cfg) => {
      // 直接走 success；不调用 chunk 回调
      queueMicrotask(() => {
        ;(cfg.success as (r: { statusCode: number; data: ArrayBuffer }) => void)({
          statusCode: 200,
          data: utf8Buffer('event: a\ndata: 1\n\nevent: b\ndata: 2\n\n'),
        })
      })
      return task
    })

    const { streamSSE } = await import('@/utils/sseClient')
    const events: { type: string; data: unknown }[] = []
    await new Promise<void>((resolve) => {
      streamSSE(
        { url: '/x' },
        { onEvent: (e) => events.push(e), onDone: () => resolve() },
      )
    })

    expect(events).toEqual([
      { type: 'a', data: 1 },
      { type: 'b', data: 2 },
    ])
  })

  test('HTTP statusCode >= 400 → onError 带状态码 + 业务 message', async () => {
    ;(Taro.request as jest.Mock).mockImplementation((cfg) => {
      queueMicrotask(() => {
        ;(cfg.success as (r: { statusCode: number; data: string }) => void)({
          statusCode: 502,
          data: JSON.stringify({ message: '上游 LLM 不可用' }),
        })
      })
      return { abort: jest.fn(), onChunkReceived: jest.fn() }
    })

    const { streamSSE } = await import('@/utils/sseClient')
    const errors: string[] = []
    await new Promise<void>((resolve) => {
      streamSSE(
        { url: '/x' },
        {
          onEvent: () => undefined,
          onError: (e) => {
            errors.push(e.message)
            resolve()
          },
        },
      )
    })
    expect(errors[0]).toBe('HTTP 502：上游 LLM 不可用')
  })

  test('fail 走 abort 路径 → 不再额外 onError（cancel 静默）', async () => {
    let failCb: ((err: { errMsg: string }) => void) | undefined
    const task = { abort: jest.fn(), onChunkReceived: jest.fn() }
    ;(Taro.request as jest.Mock).mockImplementation((cfg) => {
      failCb = cfg.fail as typeof failCb
      return task
    })

    const { streamSSE } = await import('@/utils/sseClient')
    const errors: { msg: string; aborted: boolean }[] = []
    const cancel = streamSSE(
      { url: '/x' },
      {
        onEvent: () => undefined,
        onError: (e, meta) => errors.push({ msg: e.message, aborted: meta.aborted }),
      },
    )

    cancel()
    // 模拟 wx 在 abort 后调 fail.errMsg = 'request:fail abort'
    failCb?.({ errMsg: 'request:fail abort' })
    await new Promise((r) => setTimeout(r, 5))

    expect(task.abort).toHaveBeenCalled()
    // 用户主动 cancel，不应再次 onError
    expect(errors).toHaveLength(0)
  })
})
