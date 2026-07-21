/**
 * PP-06：公测期价值感知卡——每日最多展示一次。
 */

import { getStorageSync, setStorageSync } from '@/adapters/kvStorage'
import { isPromoFreeActive } from '@/utils/promoFree'
import { toShanghaiDateKey } from '@/hooks/useMembershipExpiringSoonModal'
import type { User } from '@/types/api'

const STORAGE_KEY = 'promo_value_card_shown_date'

export const PROMO_VALUE_CARD_COPY = {
  title: '把进步延续到公测之后',
  body: '公测结束后，会员可继续无限分析，并查看完整进步曲线与本周训练计划。',
  cta: '了解会员权益',
} as const

/** 纯函数：是否应展示（便于 jest） */
export function shouldShowPromoValueCardPure(input: {
  promoActive: boolean
  todayDateKey: string
  lastShownDateKey: string | null
}): boolean {
  if (!input.promoActive) return false
  return input.lastShownDateKey !== input.todayDateKey
}

export function shouldShowPromoValueCard(user?: User | null): boolean {
  const today = toShanghaiDateKey(Date.now())
  let last: string | null = null
  try {
    const raw = getStorageSync(STORAGE_KEY)
    last = typeof raw === 'string' && raw.length > 0 ? raw : null
  } catch {
    last = null
  }
  return shouldShowPromoValueCardPure({
    promoActive: isPromoFreeActive(user),
    todayDateKey: today,
    lastShownDateKey: last,
  })
}

export function markPromoValueCardShown(): void {
  try {
    setStorageSync(STORAGE_KEY, toShanghaiDateKey(Date.now()))
  } catch {
    // ignore
  }
}
