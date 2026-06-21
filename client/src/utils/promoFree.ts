/**
 * 公测免费（PROMO_FREE_UNTIL）客户端辅助。
 * 登录后以 /users/me.promo_free 为准；未登录时可读编译期 TARO_APP_PROMO_FREE_UNTIL。
 */

import type { PromoFreeStatus, User } from '@/types/api'
import { PROMO_FREE_UNTIL_FLAG } from '@/constants/flags'

function parseUntilEndMs(until: string): number | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(until.trim())
  if (!m) return null
  const y = Number(m[1])
  const mo = Number(m[2]) - 1
  const d = Number(m[3])
  return new Date(y, mo, d, 23, 59, 59, 999).getTime()
}

export function isPromoFreeUntilActive(until: string | null | undefined): boolean {
  if (!until) return false
  const end = parseUntilEndMs(until)
  if (end == null) return false
  return Date.now() <= end
}

export function resolvePromoFreeStatus(user?: User | null): PromoFreeStatus | null {
  if (user?.promo_free) return user.promo_free
  if (!PROMO_FREE_UNTIL_FLAG) return null
  const active = isPromoFreeUntilActive(PROMO_FREE_UNTIL_FLAG)
  if (!active) return null
  return {
    active: true,
    until: PROMO_FREE_UNTIL_FLAG,
    message: `公测免费至 ${PROMO_FREE_UNTIL_FLAG}`,
  }
}

export function isPromoFreeActive(user?: User | null): boolean {
  return resolvePromoFreeStatus(user)?.active === true
}

/** 展示用，如「公测免费至 7 月 30 日」 */
export function promoFreeBannerText(user?: User | null): string | null {
  const status = resolvePromoFreeStatus(user)
  if (!status?.active) return null
  if (status.message) return status.message
  if (status.until) {
    const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(status.until)
    if (m) return `公测免费至 ${Number(m[2])} 月 ${Number(m[3])} 日`
  }
  return '公测免费中'
}
