import Taro from '@tarojs/taro'
import { storage } from '@/utils/storage'
import type { APIResponse } from '@/types/api'

declare const API_BASE_URL: string

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
 * 统一请求封装。
 * - 自动注入 Bearer Token
 * - 自动按统一响应格式 { code, message, data } 解包
 * - code !== 0 视为业务错误，抛 Error，由调用方决定是否 toast
 * - 401 自动清除 Token 并跳转登录
 */
export async function request<T = unknown>(opts: RequestOptions): Promise<T> {
  const baseURL = API_BASE_URL || 'http://localhost:8000/v1'
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

  try {
    const res = await Taro.request<APIResponse<T>>({
      url,
      method: opts.method || 'GET',
      data: opts.data,
      header,
      timeout: opts.timeout || 15000
    })

    // HTTP 层错误
    if (res.statusCode >= 500) {
      if (!opts.silent) {
        Taro.showToast({ title: '服务暂时不可用', icon: 'none' })
      }
      throw new Error(`HTTP ${res.statusCode}`)
    }

    if (res.statusCode === 401) {
      storage.clearToken()
      Taro.reLaunch({ url: '/pages/login/index' })
      throw new Error('未登录或登录已过期')
    }

    const body = res.data
    if (!body || typeof body.code !== 'number') {
      throw new Error('响应格式错误')
    }

    if (body.code !== 0) {
      if (!opts.silent) {
        Taro.showToast({ title: body.message || '请求失败', icon: 'none' })
      }
      const err = new Error(body.message || '业务错误') as Error & { code?: number }
      err.code = body.code
      throw err
    }

    return body.data as T
  } catch (e: unknown) {
    if (!opts.silent) {
      const msg = e instanceof Error ? e.message : '网络异常'
      console.warn('[request]', opts.url, msg)
    }
    throw e
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
