/**
 * 埋点 / 错误上报客户端（W8-T5）
 *
 * 设计要点
 * --------
 * 1. 入队 → 定时 flush：调用方写 `track(name, payload)` 只是入队，不直接发网络
 * 2. Flush 触发条件（任一命中）：
 *    - 队列长度 ≥ `MAX_BATCH_SIZE`（默认 20）
 *    - 距上次 flush 超过 `FLUSH_INTERVAL_MS`（默认 5s）
 *    - 显式 `flushTrack()`（如应用退到后台）
 *    - error_report 会 **立即 flush**（错误不能等 5s）
 * 3. 失败重试：单次 flush 失败把事件塞回队头，下次 flush 时再试；
 *    连续失败 3 次就丢弃这批（避免无限增长），并打一条 console.warn
 * 4. 存储：进程内内存数组；关 app 会丢——本期接受；W9 有余力再接 storage
 *
 * 事件名白名单
 * ------------
 * 见 `EVENT_NAMES`；与后端 `event_service.py::EVENT_NAMES` 一致。
 * 非白名单事件会在后端被 rejected（前端不做前置校验，让白名单只在一处维护）
 */

import Taro from '@tarojs/taro'
import { storage } from '@/utils/storage'

declare const API_BASE_URL: string
declare const APP_ENV: string

/**
 * W8 内测专用：在 `APP_ENV === 'test'` 时彻底跳过埋点上报。
 * 原因：`/events` 失败重试会在控制台抛 `Error: timeout`，把真正
 * 业务报错淹没在红色噪音里，干扰真机调试。
 *
 * 接通正式上线时把这个开关去掉、或加白名单环境即可。
 */
const TRACK_DISABLED = (() => {
  try {
    return typeof APP_ENV !== 'undefined' && APP_ENV === 'test'
  } catch {
    return false
  }
})()

export type EventName =
  | 'page_view'
  | 'analysis_submit'
  | 'analysis_done'
  | 'share_report'
  | 'pay_success'
  | 'error_report'
  /** PP-05：进入会员中心 */
  | 'membership_view'
  /** PP-05：点击开通/续费 CTA */
  | 'upgrade_cta_click'

interface TrackPayload {
  name: EventName
  payload?: Record<string, unknown> | unknown[]
  client_ts: number
}

const MAX_BATCH_SIZE = 20
const FLUSH_INTERVAL_MS = 5000
const MAX_RETRY = 3

let queue: TrackPayload[] = []
let timer: ReturnType<typeof setTimeout> | null = null
let retryCount = 0
let flushing = false

/**
 * 记录一个埋点事件。
 *
 * 调用安全：本函数永远不会抛异常；内部捕获所有错误。
 * `error_report` 事件会触发立即 flush。
 */
export function track(
  name: EventName,
  payload?: Record<string, unknown> | unknown[],
): void {
  if (TRACK_DISABLED) return
  try {
    queue.push({
      name,
      payload,
      client_ts: Date.now(),
    })

    if (name === 'error_report') {
      // 错误事件优先发出，别等 5s 定时器
      void flushTrack()
      return
    }

    if (queue.length >= MAX_BATCH_SIZE) {
      void flushTrack()
      return
    }

    scheduleFlush()
  } catch {
    // 埋点不该影响主流程
  }
}

/**
 * 立即 flush 队列。返回 promise 方便测试；调用方无需 await。
 */
export async function flushTrack(): Promise<void> {
  if (TRACK_DISABLED) {
    queue = []
    return
  }
  if (flushing) return
  if (queue.length === 0) return

  flushing = true
  // 原子抓取当前批次；新事件进入新队列
  const batch = queue.splice(0, MAX_BATCH_SIZE)
  clearTimer()

  try {
    const baseURL = API_BASE_URL || 'http://localhost:8000/v1'
    const header: Record<string, string> = { 'Content-Type': 'application/json' }
    const token = storage.getToken()
    if (token) header.Authorization = `Bearer ${token}`

    const res = await Taro.request({
      url: `${baseURL}/events`,
      method: 'POST',
      header,
      data: { events: batch },
      timeout: 8000,
    })

    if (res.statusCode >= 500) {
      throw new Error(`events_5xx_${res.statusCode}`)
    }
    retryCount = 0
  } catch (e) {
    // 失败：塞回队头，累计重试次数
    queue = [...batch, ...queue]
    retryCount += 1
    if (retryCount >= MAX_RETRY) {
      // 连续失败 3 次 → 放弃这批，避免内存涨到天花板
      queue = queue.slice(batch.length)
      retryCount = 0
      const reason =
        e instanceof Error && e.message
          ? e.message
          : typeof e === 'string'
            ? e
            : e != null && typeof (e as { errMsg?: string }).errMsg === 'string'
              ? (e as { errMsg: string }).errMsg
              : String(e)
      // eslint-disable-next-line no-console
      console.warn('[track] drop batch after retries:', reason)
    } else {
      scheduleFlush()
    }
  } finally {
    flushing = false
    // 若刚 flush 完队列又填满，立刻再试
    if (queue.length >= MAX_BATCH_SIZE) {
      void flushTrack()
    } else if (queue.length > 0) {
      scheduleFlush()
    }
  }
}

function scheduleFlush(): void {
  if (timer) return
  timer = setTimeout(() => {
    timer = null
    void flushTrack()
  }, FLUSH_INTERVAL_MS)
}

function clearTimer(): void {
  if (timer) {
    clearTimeout(timer)
    timer = null
  }
}

/**
 * 便捷：记录一个运行期错误。
 * 只保留信息量大、PII 少的字段，避免把用户输入无意识泄露到埋点表。
 */
export function trackError(err: unknown, context?: Record<string, unknown>): void {
  const payload: Record<string, unknown> = {
    ...(context || {}),
    message: err instanceof Error ? err.message : String(err),
  }
  if (err instanceof Error && err.stack) {
    // 只保留前 2KB 栈，避免单事件过大被后端截断
    payload.stack = err.stack.slice(0, 2048)
  }
  track('error_report', payload)
}
