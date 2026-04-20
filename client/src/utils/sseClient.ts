/**
 * SSE（Server-Sent Events）客户端封装
 *
 * 设计目标：
 *   - 小程序：走 `Taro.request({ enableChunked: true }) + task.onChunkReceived`
 *     （需要微信基础库 ≥ 2.20.1 并支持 `request.object.enableChunked`）
 *   - H5：走原生 `fetch + response.body.getReader()`
 *   - 暴露统一签名 `streamSSE(options, handlers): cancel`
 *   - **不做伪流式降级**：基础库不支持 chunked 时直接抛错，让上层提示用户升级微信
 *     —— 理由见 docs/13 T4："MVP 不做代码分叉，future work 里再加 polling 降级"
 *
 * 事件格式（与后端 `backend/app/api/v1/chat.py::_sse_event_stream` 对齐）：
 *
 *   event: content_delta\n
 *   data: {"delta":"好的"}\n
 *   \n
 *
 * 解析要点：
 *   1. `\n\n` 分 event；最后一个不完整的留在 buffer 等下次拼接
 *   2. 每个 event 内按 `\n` 分行：`event:` 取事件名，`data:` 取 payload；
 *      data 可多行，拼接时用 `\n` 连接（但我们后端不会多行 data，保留兼容代码即可）
 *   3. 增量 utf-8 解码：微信 2.21+ 有 TextDecoder；老版本 fallback 到手写解码器
 *      （中文消息必须按字节边界增量解码，否则一个汉字被拆到两 chunk 时会乱码）
 */

import Taro from '@tarojs/taro'
import { storage } from '@/utils/storage'

declare const API_BASE_URL: string

export interface SSEEvent<T = unknown> {
  /** 对应后端 `event: xxx`；默认 `message` */
  type: string
  /** `data:` 部分解析成的 JSON；若不是合法 JSON 则为原始字符串 */
  data: T
}

export interface StreamSSEOptions {
  /** 路径或完整 URL；以 `/` 开头时会自动拼 `API_BASE_URL` */
  url: string
  method?: 'POST' | 'GET'
  body?: unknown
  /** 额外 header；Bearer Token / Accept 本封装会自动带 */
  header?: Record<string, string>
  /** 整个流的超时（包含 LLM 生成时间）；默认 60s */
  timeoutMs?: number
  /** 不自动注入 Bearer Token */
  noAuth?: boolean
}

export interface StreamSSEHandlers<T = unknown> {
  /** 每个 SSE 事件到达时回调；**按后端推送顺序串行调用** */
  onEvent(event: SSEEvent<T>): void
  /** 传输层错误（超时 / 被 abort / HTTP 非 2xx / 解析崩溃）；**不包含业务 error 事件** */
  onError?(err: Error, meta: { aborted: boolean }): void
  /** 整个流正常结束（连接关闭 / last chunk 收完） */
  onDone?(): void
}

export type StreamCancel = () => void

/* ==================== 入口 ==================== */
export function streamSSE<T = unknown>(
  options: StreamSSEOptions,
  handlers: StreamSSEHandlers<T>,
): StreamCancel {
  if (process.env.TARO_ENV === 'h5') {
    return streamH5(options, handlers)
  }
  return streamWeapp(options, handlers)
}

/* ==================== 小程序实现 ==================== */
function streamWeapp<T>(
  opts: StreamSSEOptions,
  handlers: StreamSSEHandlers<T>,
): StreamCancel {
  const wxApi = typeof wx !== 'undefined' ? wx : undefined
  if (!wxApi?.canIUse?.('request.object.enableChunked')) {
    queueMicrotask(() =>
      handlers.onError?.(
        new Error('当前微信版本不支持流式对话，请升级到最新版微信'),
        { aborted: false },
      ),
    )
    return () => undefined
  }

  const url = buildUrl(opts.url)
  const header = buildHeaders(opts)
  let aborted = false
  let done = false
  // Taro.RequestTask 类型在 enableChunked 场景下字段不全；这里用 any 放宽
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let task: any
  const parser = new SSEParser<T>()

  // 超时：本地设一次 setTimeout；到点就 abort
  const timeoutMs = opts.timeoutMs ?? 60000
  const timer = setTimeout(() => {
    if (!done && !aborted) {
      aborted = true
      try {
        task?.abort()
      } catch {
        // 忽略 abort 失败
      }
      handlers.onError?.(new Error('对话请求超时'), { aborted: true })
    }
  }, timeoutMs)

  try {
    // Taro.request 在 enableChunked=true 时返回 RequestTask（同步）；
    // Taro 的类型签名里没有 enableChunked / responseType:'text' 等字段，
    // 这里用 any 旁路掉（微信官方 wx.request 支持这些参数）。
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    task = (Taro.request as any)({
      url,
      method: opts.method ?? 'POST',
      data: opts.body as Record<string, unknown> | undefined,
      header,
      enableChunked: true,
      // 任意 2xx 都继续解析；非 2xx 由下方 statusCode 分支兜底
      responseType: 'text',
      timeout: timeoutMs,
      success: (res) => {
        // success 在所有 chunk 收完后触发；这里只用来决定最终状态
        if (aborted || done) return
        done = true
        clearTimeout(timer)
        if (res.statusCode >= 400) {
          // 服务器返回的是 JSON 错误（被 SSE 的 Content-Type 误判时可能直接走到这里）
          handlers.onError?.(
            new Error(`HTTP ${res.statusCode}：${extractErrMsg(res.data)}`),
            { aborted: false },
          )
          return
        }
        // 尝试 flush 最后一段 buffer
        parser.flush().forEach((evt) => handlers.onEvent(evt))
        handlers.onDone?.()
      },
      fail: (err) => {
        if (done) return
        done = true
        clearTimeout(timer)
        // `abort` 会触发 fail.errMsg = 'request:fail abort'
        const isAbort = /abort/i.test(err.errMsg || '')
        if (aborted || isAbort) {
          // 调用方主动取消的场景；上层一般不需要再 onError
          if (!aborted) {
            handlers.onError?.(new Error('连接已中断'), { aborted: true })
          }
          return
        }
        handlers.onError?.(new Error(err.errMsg || '网络异常'), {
          aborted: false,
        })
      },
    })

    // 注册 chunk 回调；每次 res.data 是 ArrayBuffer
    task?.onChunkReceived?.((res: { data: ArrayBuffer }) => {
      if (aborted || done) return
      try {
        const events = parser.feed(res.data)
        events.forEach((evt) => handlers.onEvent(evt))
      } catch (e) {
        done = true
        clearTimeout(timer)
        try {
          task?.abort()
        } catch {
          // ignore
        }
        handlers.onError?.(
          new Error(e instanceof Error ? e.message : 'SSE 解析异常'),
          { aborted: false },
        )
      }
    })
  } catch (e) {
    clearTimeout(timer)
    handlers.onError?.(
      new Error(e instanceof Error ? e.message : '发起请求失败'),
      { aborted: false },
    )
  }

  return () => {
    if (done || aborted) return
    aborted = true
    clearTimeout(timer)
    try {
      task?.abort()
    } catch {
      // ignore
    }
  }
}

/* ==================== H5 fetch 实现 ==================== */
function streamH5<T>(
  opts: StreamSSEOptions,
  handlers: StreamSSEHandlers<T>,
): StreamCancel {
  const url = buildUrl(opts.url)
  const header = buildHeaders(opts)
  const controller = new AbortController()
  let done = false
  const timeoutMs = opts.timeoutMs ?? 60000
  const timer = setTimeout(() => {
    if (!done) {
      controller.abort()
      handlers.onError?.(new Error('对话请求超时'), { aborted: true })
    }
  }, timeoutMs)

  ;(async () => {
    try {
      const res = await fetch(url, {
        method: opts.method ?? 'POST',
        headers: header,
        body: opts.body ? JSON.stringify(opts.body) : undefined,
        signal: controller.signal,
      })

      if (!res.ok) {
        done = true
        clearTimeout(timer)
        const text = await res.text().catch(() => '')
        handlers.onError?.(
          new Error(`HTTP ${res.status}：${extractErrMsg(text)}`),
          { aborted: false },
        )
        return
      }
      if (!res.body) {
        done = true
        clearTimeout(timer)
        handlers.onError?.(new Error('流式响应无 body'), { aborted: false })
        return
      }

      const reader = res.body.getReader()
      const parser = new SSEParser<T>()
      while (true) {
        const { value, done: reading } = await reader.read()
        if (reading) break
        if (!value) continue
        parser.feed(value.buffer as ArrayBuffer).forEach((evt) =>
          handlers.onEvent(evt),
        )
      }
      parser.flush().forEach((evt) => handlers.onEvent(evt))
      done = true
      clearTimeout(timer)
      handlers.onDone?.()
    } catch (err) {
      if (done) return
      done = true
      clearTimeout(timer)
      const aborted = (err as Error)?.name === 'AbortError'
      handlers.onError?.(
        new Error(aborted ? '连接已中断' : (err as Error)?.message || '网络异常'),
        { aborted },
      )
    }
  })()

  return () => {
    if (!done) {
      done = true
      clearTimeout(timer)
      controller.abort()
    }
  }
}

/* ==================== SSE 帧解析器 ==================== */

/**
 * 增量解析 SSE 字节流。
 *
 * 用法：
 *   const parser = new SSEParser()
 *   parser.feed(chunk) // 返回已解析完整事件列表
 *   parser.flush()     // 流结束时 flush 可能残留的最后一段（通常为空）
 */
class SSEParser<T> {
  private decoder = new Utf8StreamDecoder()
  private textBuffer = ''

  feed(chunk: ArrayBuffer): SSEEvent<T>[] {
    this.textBuffer += this.decoder.decode(chunk)
    return this.extract()
  }

  flush(): SSEEvent<T>[] {
    // 末尾的 tail：如果还剩一段完整事件（比如最后一个事件后端忘加 \n\n），也当成一个事件
    const tail = this.textBuffer.trim()
    this.textBuffer = ''
    if (!tail) return []
    return [parseBlock<T>(tail)].filter(Boolean) as SSEEvent<T>[]
  }

  private extract(): SSEEvent<T>[] {
    const out: SSEEvent<T>[] = []
    let idx: number
    // 用 \n\n 或 \r\n\r\n 作为分隔（后者兼容某些代理改写）
    while (true) {
      const n1 = this.textBuffer.indexOf('\n\n')
      const n2 = this.textBuffer.indexOf('\r\n\r\n')
      if (n1 === -1 && n2 === -1) break
      let sepLen = 2
      idx = n1 !== -1 && (n2 === -1 || n1 < n2) ? n1 : n2
      if (idx === n2) sepLen = 4
      const block = this.textBuffer.slice(0, idx)
      this.textBuffer = this.textBuffer.slice(idx + sepLen)
      const evt = parseBlock<T>(block)
      if (evt) out.push(evt)
    }
    return out
  }
}

function parseBlock<T>(block: string): SSEEvent<T> | null {
  const lines = block.split(/\r?\n/)
  let eventType = 'message'
  const dataLines: string[] = []
  for (const raw of lines) {
    const line = raw.trimEnd()
    if (!line || line.startsWith(':')) continue // 空行或注释
    if (line.startsWith('event:')) {
      eventType = line.slice(6).trim()
    } else if (line.startsWith('data:')) {
      // spec 规定去掉 `data:` 后如果还有前导空格，也去掉一个
      dataLines.push(line.slice(5).replace(/^ /, ''))
    }
    // 其它 `id:` / `retry:` 等 SSE 字段本期不处理
  }
  if (!dataLines.length) return null
  const rawData = dataLines.join('\n')
  let parsed: unknown = rawData
  try {
    parsed = JSON.parse(rawData)
  } catch {
    // 非 JSON 就原样返回
  }
  return { type: eventType, data: parsed as T }
}

/* ==================== UTF-8 增量解码 ====================
 * 目的：一个汉字跨 chunk 边界时不能被错误截断。
 * - 优先用平台 TextDecoder（stream 模式自动处理残字节）
 * - 微信老版本没有 TextDecoder → 手写一个：把尾部不完整的 utf-8 序列留到下一轮
 */

interface DecoderLike {
  decode(buf: ArrayBuffer): string
}

class Utf8StreamDecoder implements DecoderLike {
  private impl: DecoderLike
  constructor() {
    if (typeof TextDecoder !== 'undefined') {
      const td = new TextDecoder('utf-8', { fatal: false })
      this.impl = {
        decode(buf: ArrayBuffer) {
          return td.decode(new Uint8Array(buf), { stream: true })
        },
      }
    } else {
      this.impl = new ManualUtf8Decoder()
    }
  }
  decode(buf: ArrayBuffer): string {
    return this.impl.decode(buf)
  }
}

class ManualUtf8Decoder implements DecoderLike {
  private pending = new Uint8Array(0)
  decode(buf: ArrayBuffer): string {
    // 拼接上一轮的残字节
    const cur = new Uint8Array(buf)
    const merged = new Uint8Array(this.pending.length + cur.length)
    merged.set(this.pending, 0)
    merged.set(cur, this.pending.length)
    // 从末尾往前找最近一个"完整 utf-8 字符"的边界
    let cut = merged.length
    // 往前最多回退 3 字节（utf-8 单字符最长 4 字节，首字节有标志位）
    for (let i = merged.length - 1; i >= Math.max(0, merged.length - 3); i--) {
      const b = merged[i]
      if ((b & 0x80) === 0) {
        // ASCII 单字节，截断就在这后面
        cut = i + 1
        break
      }
      if ((b & 0xc0) === 0xc0) {
        // 多字节首字节
        const expected =
          (b & 0xe0) === 0xc0 ? 2 : (b & 0xf0) === 0xe0 ? 3 : 4
        const have = merged.length - i
        cut = have >= expected ? merged.length : i
        break
      }
      // 继续往前找（当前是中间字节 10xxxxxx）
    }
    const toDecode = merged.slice(0, cut)
    this.pending = merged.slice(cut)
    return decodeUtf8Bytes(toDecode)
  }
}

function decodeUtf8Bytes(bytes: Uint8Array): string {
  // 纯 JS utf-8 → String；兼容基础库极老版本
  let out = ''
  let i = 0
  while (i < bytes.length) {
    const b1 = bytes[i++]
    if (b1 < 0x80) {
      out += String.fromCharCode(b1)
    } else if (b1 < 0xe0) {
      const b2 = bytes[i++] & 0x3f
      out += String.fromCharCode(((b1 & 0x1f) << 6) | b2)
    } else if (b1 < 0xf0) {
      const b2 = bytes[i++] & 0x3f
      const b3 = bytes[i++] & 0x3f
      out += String.fromCharCode(((b1 & 0x0f) << 12) | (b2 << 6) | b3)
    } else {
      const b2 = bytes[i++] & 0x3f
      const b3 = bytes[i++] & 0x3f
      const b4 = bytes[i++] & 0x3f
      let code =
        ((b1 & 0x07) << 18) | (b2 << 12) | (b3 << 6) | b4
      code -= 0x10000
      out += String.fromCharCode(0xd800 + (code >> 10))
      out += String.fromCharCode(0xdc00 + (code & 0x3ff))
    }
  }
  return out
}

/* ==================== util ==================== */
function buildUrl(path: string): string {
  if (path.startsWith('http')) return path
  const base = (typeof API_BASE_URL !== 'undefined' && API_BASE_URL)
    ? API_BASE_URL
    : 'http://localhost:8000/v1'
  return `${base}${path}`
}

function buildHeaders(opts: StreamSSEOptions): Record<string, string> {
  const header: Record<string, string> = {
    'Content-Type': 'application/json',
    Accept: 'text/event-stream',
    ...(opts.header || {}),
  }
  if (!opts.noAuth) {
    const token = storage.getToken()
    if (token) header.Authorization = `Bearer ${token}`
  }
  return header
}

function extractErrMsg(data: unknown): string {
  if (!data) return ''
  try {
    const obj = typeof data === 'string' ? JSON.parse(data) : data
    if (obj && typeof obj === 'object' && 'message' in obj) {
      return String((obj as { message: unknown }).message)
    }
  } catch {
    // not json
  }
  const s = typeof data === 'string' ? data : JSON.stringify(data)
  return s.length > 120 ? `${s.slice(0, 117)}...` : s
}
