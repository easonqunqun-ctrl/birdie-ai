import Taro from '@tarojs/taro'
import { storage } from '@/utils/storage'
import type { APIResponse } from '@/types/api'
import { formatWxDomainComplianceError } from '@/utils/wxDomainMessages'

export interface RequestOptions {
  url: string
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH'
  data?: Record<string, unknown> | unknown[]
  header?: Record<string, string>
  timeout?: number
  /** 不自动加 Bearer Token */
  noAuth?: boolean
  /** 不自动 toast 错误 */
  silent?: boolean
}

/**
 * 统一请求异常。
 * 调用方可通过 `kind` 字段区分错误类别，按需做不同处理。
 *   - http_unauthorized (401)：身份失效，应清 token 并跳登录
 *   - http_server_error (5xx)：后端故障，可重试
 *   - business：HTTP 200 但业务码非 0（含 quota_exhausted、rate_limit 等）
 *   - bad_response：响应包结构异常
 *   - network：网络/超时/小程序 wx.request 自身错误
 *
 * 关键作用：让 `userStore.bootstrap` 等调用方避免「任何失败都清 token」的误杀。
 */
export class RequestError extends Error {
  kind:
    | 'http_unauthorized'
    | 'http_server_error'
    | 'business'
    | 'bad_response'
    | 'network'
  status?: number
  code?: number
  /** 后端统一信封里的 `detail`（如支付 50201 的具体异常文本） */
  detail?: string | null
  /** 与后端 JSON `request_id` / 响应头 `X-Request-ID` 对齐，便于 grep 日志 */
  requestId?: string
  constructor(
    kind: RequestError['kind'],
    message: string,
    extra?: {
      status?: number
      code?: number
      detail?: string | null
      requestId?: string
    },
  ) {
    super(message)
    this.kind = kind
    this.status = extra?.status
    this.code = extra?.code
    this.detail = extra?.detail
    this.requestId = extra?.requestId
  }
}

export function isRequestError(e: unknown): e is RequestError {
  return e instanceof RequestError
}

function extractResponseRequestId(
  headers: Record<string, unknown> | undefined,
  body: Partial<APIResponse<unknown>> | undefined,
): string | undefined {
  const fromBody =
    body &&
    typeof body.request_id === 'string' &&
    body.request_id.trim()
      ? body.request_id.trim()
      : ''
  if (fromBody) return fromBody
  if (!headers || typeof headers !== 'object') return undefined
  const h = headers as Record<string, string>
  const raw =
    h['x-request-id'] ??
    h['X-Request-Id'] ??
    h['X-Request-ID']
  const v = typeof raw === 'string' ? raw.trim() : ''
  return v || undefined
}

/** 解析 `Taro.request` / `wx.request` 失败时的对象（往往不是标准 Error）。 */
function extractWxFailMessage(e: unknown): string {
  if (typeof e === 'string' && e.trim()) return e.trim()
  if (e instanceof Error && e.message) return e.message.trim()
  if (e && typeof e === 'object') {
    const o = e as Record<string, unknown>
    if (typeof o.errMsg === 'string' && o.errMsg.trim()) return o.errMsg.trim()
    if (typeof o.message === 'string' && o.message.trim()) return o.message.trim()
  }
  return ''
}

/** 证书/TLS 失败（真机 Cronet 常为 errcode:-207；模拟器有时不报） */
function isLikelyTlsCertFailure(raw: string): boolean {
  const lower = raw.toLowerCase()
  return (
    lower.includes('errcode:-207') ||
    lower.includes('cronet_error_code') ||
    lower.includes('err_cert_invalid') ||
    lower.includes('err_cert_authority_invalid') ||
    lower.includes('err_cert_common_name_invalid') ||
    lower.includes('net::err_cert') ||
    lower.includes('certificate_verify_failed') ||
    lower.includes('ssl handshake') ||
    lower.includes('tls alert') ||
    lower.includes('unknown ca') ||
    lower.includes('unable to verify') ||
    lower.includes('pkix') ||
    lower.includes('cert_verify_failed') ||
    lower.includes('self signed') ||
    lower.includes('self-signed certificate') ||
    raw.includes('证书') ||
    lower.includes('err_ssl')
  )
}

/** 证书问题专用提示（toast 单行；运维详见 infra/deploy/README.md） */
function tlsCertFailureUserHint(): string {
  return "HTTPS 证书校验失败：请使用公信 CA（如 Let's Encrypt），并部署完整证书链"
}

/** 体验版 / 真机常见：域名、证书、超时 —— 转成用户可理解的短句 */
function friendlyNetworkMessage(raw: string, requestUrl?: string): string {
  const r = raw.trim()
  if (!r) return '网络异常，请稍后重试'

  const lower = r.toLowerCase()

  if (
    lower.includes('not in domain list') ||
    r.includes('合法域名') ||
    lower.includes('domain list')
  ) {
    return formatWxDomainComplianceError('request', raw, requestUrl)
  }

  if (isLikelyTlsCertFailure(r)) {
    return tlsCertFailureUserHint()
  }

  if (lower.includes('timeout') || r.includes('超时')) {
    return '请求超时，请检查网络与接口是否可达'
  }

  if (lower.includes('fail') && (lower.includes('connect') || lower.includes('connection'))) {
    return '无法连接服务器，请确认域名解析与防火墙'
  }

  return r.length > 56 ? `${r.slice(0, 55)}…` : r
}

/**
 * 统一请求封装。
 * - 自动注入 Bearer Token
 * - 自动按统一响应格式 { code, message, data } 解包
 * - code !== 0 视为业务错误，抛 Error，由调用方决定是否 toast
 * - 401 自动清除 Token 并跳转登录
 */
export async function request<T = unknown>(opts: RequestOptions): Promise<T> {
  const trimmed = typeof API_BASE_URL === 'string' ? API_BASE_URL.trim() : ''
  const baseURL =
    trimmed ||
    (APP_ENV === 'production' ? '' : 'http://localhost:8000/v1')
  if (!baseURL) {
    throw new RequestError(
      'network',
      'API 地址未配置：请检查构建变量 TARO_APP_API_BASE_URL（须含 /v1）',
    )
  }
  const url = opts.url.startsWith('http') ? opts.url : `${baseURL}${opts.url}`

  const header: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(opts.header || {})
  }

  if (!opts.noAuth) {
    const token = storage.getToken()
    if (token) {
      header.Authorization = `Bearer ${token}`
    }
  }

  let res: {
    statusCode: number
    data: APIResponse<T>
    header?: Record<string, unknown>
  }
  try {
    res = await Taro.request<APIResponse<T>>({
      url,
      method: opts.method || 'GET',
      data: opts.data,
      header,
      timeout: opts.timeout || 15000
    })
  } catch (e: unknown) {
    const raw = extractWxFailMessage(e)
    const msg = friendlyNetworkMessage(raw, url)
    if (!opts.silent) {
      console.warn('[request:network]', url, raw || e)
    }
    throw new RequestError('network', msg)
  }

  if (res.statusCode === 401) {
    const maybe = res.data as Partial<APIResponse<unknown>>
    const bizCode = typeof maybe.code === 'number' ? maybe.code : undefined
    // 微信 wx.login code 过期 / 重复使用：HTTP 亦为 401，但语义是「换码重试」，不是 JWT 失效
    if (bizCode === 40104) {
      const msg = typeof maybe.message === 'string' && maybe.message.trim()
        ? maybe.message.trim()
        : '微信登录凭证已失效，请再点一次登录'
      if (!opts.silent) {
        Taro.showToast({ title: msg, icon: 'none', duration: 2800 })
      }
      throw new RequestError('business', msg, { status: 401, code: bizCode })
    }

    // 其余 401：按既有 JWT 失效处理
    handleUnauthorized()
    throw new RequestError('http_unauthorized', '未登录或登录已过期', {
      status: 401,
    })
  }

  /**
   * 5xx 网关/进程错误 —— 但若 body 仍是统一 JSON 信封（如 AIChatServiceError → HTTP 502 + code 50106），
   * 必须按业务错误抛出，否则对话页只能看到「HTTP 502」而无法走 50106 的专门提示与重试语义。
   */
  if (res.statusCode >= 500) {
    const maybe = res.data as Partial<APIResponse<unknown>> | string | null | undefined
    const rid500 =
      maybe && typeof maybe === 'object'
        ? extractResponseRequestId(res.header, maybe)
        : extractResponseRequestId(res.header, undefined)
    if (
      maybe &&
      typeof maybe === 'object' &&
      typeof maybe.code === 'number' &&
      maybe.code !== 0
    ) {
      const raw =
        typeof maybe.message === 'string' ? maybe.message.trim() : ''
      const msg = raw || '服务暂时不可用'
      const detailRaw =
        typeof maybe.detail === 'string' ? maybe.detail.trim() : ''
      if (!opts.silent && rid500) {
        console.warn('[request:server]', opts.url, msg, 'request_id=', rid500)
      }
      if (!opts.silent) {
        Taro.showToast({ title: msg, icon: 'none' })
      }
      throw new RequestError('business', msg, {
        status: res.statusCode,
        code: maybe.code,
        detail: detailRaw || null,
        requestId: rid500,
      })
    }
    if (!opts.silent && rid500) {
      console.warn('[request:http]', opts.url, res.statusCode, 'request_id=', rid500)
    }
    if (!opts.silent) {
      Taro.showToast({ title: '服务暂时不可用', icon: 'none' })
    }
    throw new RequestError('http_server_error', `HTTP ${res.statusCode}`, {
      status: res.statusCode,
      requestId: rid500,
    })
  }

  const body = res.data
  if (!body || typeof body.code !== 'number') {
    const ridBad = extractResponseRequestId(res.header, undefined)
    if (!opts.silent) {
      console.warn('[request:bad_response]', opts.url, body, ridBad ? `request_id=${ridBad}` : '')
    }
    throw new RequestError('bad_response', '响应格式错误', {
      status: res.statusCode,
      requestId: ridBad,
    })
  }

  if (body.code !== 0) {
    const ridBiz = extractResponseRequestId(res.header, body)
    if (!opts.silent && body.code === 50001 && ridBiz) {
      console.warn('[request:business]', opts.url, body.message, 'request_id=', ridBiz)
    }
    if (!opts.silent) {
      Taro.showToast({ title: body.message || '请求失败', icon: 'none' })
    }
    const detailBiz =
      typeof body.detail === 'string' ? body.detail.trim() : ''
    throw new RequestError('business', body.message || '业务错误', {
      status: res.statusCode,
      code: body.code,
      detail: detailBiz || null,
      requestId: ridBiz,
    })
  }

  return body.data as T
}

/**
 * 轮询、uploadFile 等与 `request()` 分叉的通路：与用户可见的错误文案对齐（证书/域名/5xx）。
 */
export function describeIntermittentRequestFailure(e: unknown): {
  fatalMessage: string
  toastTitle: string
} {
  if (isRequestError(e)) {
    if (e.kind === 'http_server_error') {
      return {
        fatalMessage: '服务暂时不可用，已暂停自动刷新',
        toastTitle: '服务暂时不可用',
      }
    }
    if (e.kind === 'bad_response') {
      return {
        fatalMessage: '服务器响应异常，已暂停自动刷新',
        toastTitle: '服务响应异常',
      }
    }
    if (e.kind === 'network' && e.message?.trim()) {
      const t = friendlyNetworkMessage(e.message, undefined)
      return { fatalMessage: t, toastTitle: t }
    }
  }
  return {
    fatalMessage: '网络似乎不太稳定，已暂停自动刷新',
    toastTitle: '网络异常，请稍后重试',
  }
}

/** 列表/详情等静态页正文：与同上 helper 对齐，去掉轮询场景专用尾缀「已暂停自动刷新」。 */
const POLL_PAUSE_SUFFIX = '，已暂停自动刷新'

export function describePageLoadFailure(e: unknown): string {
  const { fatalMessage, toastTitle } = describeIntermittentRequestFailure(e)
  return fatalMessage.endsWith(POLL_PAUSE_SUFFIX)
    ? fatalMessage.slice(0, -POLL_PAUSE_SUFFIX.length)
    : fatalMessage.length > 0
      ? fatalMessage
      : toastTitle
}

/**
 * 401 兜底：清 token 并 reLaunch 登录页。
 * 用 reLaunchedRef 简单防抖，避免多请求同时 401 触发多次 reLaunch。
 */
let _unauthorizedHandling = false
function handleUnauthorized() {
  storage.clearToken()
  if (_unauthorizedHandling) return
  _unauthorizedHandling = true
  try {
    Taro.reLaunch({ url: '/pages/login/index' })
  } finally {
    // 给跳转留出时间窗，避免短时间内重复触发；reLaunch 不会回到本页，所以不必复位
    setTimeout(() => {
      _unauthorizedHandling = false
    }, 2000)
  }
}

/* ==================== 快捷方法 ==================== */
export const http = {
  get: <T = unknown>(url: string, opts?: Omit<RequestOptions, 'url' | 'method'>) =>
    request<T>({ ...(opts || {}), url, method: 'GET' }),
  post: <T = unknown>(url: string, data?: unknown, opts?: Omit<RequestOptions, 'url' | 'method' | 'data'>) =>
    request<T>({ ...(opts || {}), url, method: 'POST', data: data as Record<string, unknown> }),
  patch: <T = unknown>(url: string, data?: unknown, opts?: Omit<RequestOptions, 'url' | 'method' | 'data'>) =>
    request<T>({ ...(opts || {}), url, method: 'PATCH', data: data as Record<string, unknown> }),
  put: <T = unknown>(url: string, data?: unknown, opts?: Omit<RequestOptions, 'url' | 'method' | 'data'>) =>
    request<T>({ ...(opts || {}), url, method: 'PUT', data: data as Record<string, unknown> }),
  del: <T = unknown>(url: string, opts?: Omit<RequestOptions, 'url' | 'method'>) =>
    request<T>({ ...(opts || {}), url, method: 'DELETE' })
}
