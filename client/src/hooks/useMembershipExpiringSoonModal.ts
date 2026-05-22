/**
 * 会员到期前站内弹窗（docs/02 §1.4.3 配套；docs/19 §6.3 Q-B1 余量）.
 *
 * 设计要点
 * --------
 * - **不依赖**微信订阅消息授权配额；订阅消息一次性配额耗尽 / 用户拒绝 / 模板未配置 时仍可触达。
 * - 触发窗口 `[1, MAX_WINDOW_DAYS]` 天（默认 [1, 7]，覆盖产品 §3.5 的 7/3/1 三档预期与其他临界日）。
 * - **每日仅弹一次**：localStorage 按 `expires_at` 的日期键去重；当日点过即使重启小程序也不再弹。
 * - 函数纯逻辑、易于 jest：`shouldShowExpiringSoonModal()` 不依赖 Taro / Date.now 间接传入。
 * - 调用层：`pages/index/index.tsx` / `pages/training/index.tsx` / `pages/profile/membership.tsx` 拉到 membership 后调用 hook。
 */

import { useEffect, useRef } from 'react'
import Taro from '@tarojs/taro'
import type { MembershipInfo } from '@/types/payment'

const STORAGE_KEY_PREFIX = 'mem_expiring_modal_shown:'
export const MIN_WINDOW_DAYS = 1
export const MAX_WINDOW_DAYS = 7

export interface ShouldShowInput {
  /** `users/me/membership` 返回的会员信息；为 null 不弹 */
  membership: MembershipInfo | null
  /** 当前时刻（ms 时间戳）；测试可注入 */
  nowMs: number
  /** 本机时区与上海一致即可；仅按自然日（YYYY-MM-DD）粒度对比 */
  todayDateKey: string
  /** localStorage 已弹过的日期键集合 */
  shownKeys: Set<string>
}

export interface ShouldShowResult {
  show: boolean
  /** 剩余整自然日（向下取整）；调试用 */
  daysLeft: number
  /** 进入文案的格式化日期，例如 ``2026-05-25`` */
  expireDate: string
  /** 用于落 localStorage 的去重 key（即使本次不弹也返回，调用方不用拼） */
  dedupKey: string
}

/** 把 ms 时间戳格式化为上海时区 YYYY-MM-DD（不引 luxon / dayjs，避免分包膨胀）。
 *
 * 上海固定 UTC+8 无 DST：先把 UTC ms 平移 +8h，再用 ``getUTC*`` 取，
 * 这样不受运行环境（jsdom default UTC、不同手机时区）影响。
 */
export function toShanghaiDateKey(ms: number): string {
  const shifted = new Date(ms + 8 * 3600 * 1000)
  const y = shifted.getUTCFullYear()
  const m = String(shifted.getUTCMonth() + 1).padStart(2, '0')
  const day = String(shifted.getUTCDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

/** ``expires_at`` 解析为 ms；解析失败返回 NaN。后端固定 ISO8601 with TZ。 */
function parseExpiresAt(expires_at: string | null | undefined): number {
  if (!expires_at) return Number.NaN
  const t = Date.parse(expires_at)
  return Number.isFinite(t) ? t : Number.NaN
}

export function shouldShowExpiringSoonModal(input: ShouldShowInput): ShouldShowResult {
  const empty: ShouldShowResult = {
    show: false,
    daysLeft: -1,
    expireDate: '',
    dedupKey: '',
  }
  const mem = input.membership
  if (!mem || !mem.is_member) return empty
  if (mem.membership_type === 'free') return empty
  if (mem.auto_renew) return empty // 已开自动续费的用户不打扰

  const expMs = parseExpiresAt(mem.expires_at)
  if (!Number.isFinite(expMs)) return empty
  if (expMs <= input.nowMs) return empty // 已过期由 §1.4.2 通知接管，不重复打扰

  const expireDate = toShanghaiDateKey(expMs)
  // 用日期键之差算自然日，避免「23:59 → 00:01」算 0 天
  const diffDays = daysBetweenDateKeys(input.todayDateKey, expireDate)
  const dedupKey = `${expireDate}`
  if (diffDays < MIN_WINDOW_DAYS || diffDays > MAX_WINDOW_DAYS) {
    return { ...empty, daysLeft: diffDays, expireDate, dedupKey }
  }
  if (input.shownKeys.has(dedupKey)) {
    return { ...empty, daysLeft: diffDays, expireDate, dedupKey }
  }
  return { show: true, daysLeft: diffDays, expireDate, dedupKey }
}

/** 两个 YYYY-MM-DD 之间的整自然日差；``from > to`` 返回负数。 */
export function daysBetweenDateKeys(from: string, to: string): number {
  const a = Date.parse(`${from}T00:00:00Z`)
  const b = Date.parse(`${to}T00:00:00Z`)
  if (!Number.isFinite(a) || !Number.isFinite(b)) return 0
  return Math.round((b - a) / 86400000)
}

function readShownKeys(): Set<string> {
  try {
    const raw = Taro.getStorageSync(STORAGE_KEY_PREFIX + 'set')
    if (Array.isArray(raw)) return new Set(raw.filter((x) => typeof x === 'string'))
  } catch {
    // ignore
  }
  return new Set()
}

function persistShownKey(key: string): void {
  try {
    const cur = readShownKeys()
    cur.add(key)
    // 只保留最近 4 个 key（每月最多 4 个不同 expire_date），防止 storage 无限增长
    const arr = Array.from(cur).slice(-4)
    Taro.setStorageSync(STORAGE_KEY_PREFIX + 'set', arr)
  } catch {
    // ignore
  }
}

/** 已弹过则跳过；点完「续费」后由调用方导航到 membership 页（本 hook 只负责弹与去重）。 */
export function useMembershipExpiringSoonModal(membership: MembershipInfo | null): void {
  // 一次进入页面只允许触发一次，避免 setState 后二次 effect 重弹
  const triggeredRef = useRef(false)
  useEffect(() => {
    if (triggeredRef.current) return
    if (!membership) return
    const now = Date.now()
    const decision = shouldShowExpiringSoonModal({
      membership,
      nowMs: now,
      todayDateKey: toShanghaiDateKey(now),
      shownKeys: readShownKeys(),
    })
    if (!decision.show) return
    triggeredRef.current = true
    persistShownKey(decision.dedupKey)
    Taro.showModal({
      title: `会员还有 ${decision.daysLeft} 天到期`,
      content: `当前会员有效期至 ${decision.expireDate}。续费后权益立即恢复，进步曲线 / 历史对比等能力将持续可用。`,
      confirmText: '去续费',
      cancelText: '稍后再说',
      success: ({ confirm }) => {
        if (!confirm) return
        Taro.navigateTo({ url: '/pages/profile/membership' }).catch(() => undefined)
      },
    }).catch(() => undefined)
  }, [membership])
}
