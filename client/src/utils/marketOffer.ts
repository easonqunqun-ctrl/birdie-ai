import type { MarketOffer, User } from '@/types/api'
import { isPromoFreeActive } from '@/utils/promoFree'

export function isWelcomeOffer(user?: User | null): boolean {
  const p = user?.market_offer?.policy
  return p === 'welcome' || p === 'intl_welcome'
}

/** 不推会员付费：仅公测促销窗 */
export function shouldHideMembershipPaywall(user?: User | null): boolean {
  return isPromoFreeActive(user)
}

export function quotaBannerText(user?: User | null): string {
  if (!user?.quota) return ''
  if (user.quota.analysis_remaining < 0) {
    return '分析次数无限'
  }
  if (isWelcomeOffer(user)) {
    const n = user.market_offer?.intl_welcome_remaining ?? user.quota.analysis_remaining
    const t = user.market_offer?.intl_welcome_total ?? user.quota.analysis_total
    return `试用剩余 ${n} / ${t} 次`
  }
  if (user.is_member) return '会员·分析次数无限'
  return `本月剩余 ${user.quota.analysis_remaining} / ${user.quota.analysis_total} 次`
}

const POLICIES = new Set(['welcome', 'standard', 'cn_free', 'intl_welcome', 'intl_standard'])

export function parseMarketOffer(raw: unknown): MarketOffer | null {
  if (!raw || typeof raw !== 'object') return null
  const o = raw as Record<string, unknown>
  if (o.market !== 'cn' && o.market !== 'intl') return null
  if (typeof o.policy !== 'string' || !POLICIES.has(o.policy)) {
    return null
  }
  const policy: MarketOffer['policy'] =
    o.policy === 'intl_welcome' || o.policy === 'welcome'
      ? 'welcome'
      : o.policy === 'cn_free'
        ? 'standard'
        : o.policy === 'intl_standard'
          ? 'standard'
          : (o.policy as MarketOffer['policy'])
  return {
    market: o.market,
    policy,
    intl_welcome_remaining:
      typeof o.intl_welcome_remaining === 'number' ? o.intl_welcome_remaining : null,
    intl_welcome_total:
      typeof o.intl_welcome_total === 'number' ? o.intl_welcome_total : 100,
  }
}
