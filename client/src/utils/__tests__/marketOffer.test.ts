import {
  isWelcomeOffer,
  parseMarketOffer,
  quotaBannerText,
  shouldHideMembershipPaywall,
} from '@/utils/marketOffer'
import type { User } from '@/types/api'

function user(partial: Partial<User>): User {
  return {
    id: 'usr_x',
    nickname: null,
    avatar_url: null,
    golf_level: null,
    primary_goals: [],
    weekly_practice_frequency: null,
    membership_type: 'free',
    membership_expires_at: null,
    is_member: false,
    membership_days_remaining: 0,
    onboarding_completed: true,
    created_at: '2026-09-12T00:00:00+08:00',
    ...partial,
  }
}

describe('marketOffer', () => {
  it('欢迎包展示试用剩余，不隐藏付费', () => {
    const u = user({
      market_offer: {
        market: 'cn',
        policy: 'welcome',
        intl_welcome_remaining: 88,
        intl_welcome_total: 100,
      },
      quota: {
        analysis_remaining: 88,
        analysis_total: 100,
        analysis_reset_at: null,
        chat_remaining_today: 5,
        chat_total_today: 5,
      },
    })
    expect(isWelcomeOffer(u)).toBe(true)
    expect(quotaBannerText(u)).toBe('试用剩余 88 / 100 次')
    expect(shouldHideMembershipPaywall(u)).toBe(false)
  })

  it('标准配额展示本月剩余', () => {
    const u = user({
      market_offer: {
        market: 'intl',
        policy: 'standard',
        intl_welcome_remaining: null,
        intl_welcome_total: 100,
      },
      quota: {
        analysis_remaining: 2,
        analysis_total: 3,
        analysis_reset_at: '2026-10-01T00:00:00+08:00',
        chat_remaining_today: 5,
        chat_total_today: 5,
      },
    })
    expect(isWelcomeOffer(u)).toBe(false)
    expect(quotaBannerText(u)).toBe('本月剩余 2 / 3 次')
  })

  it('兼容旧 policy 名 intl_welcome', () => {
    const parsed = parseMarketOffer({
      market: 'intl',
      policy: 'intl_welcome',
      intl_welcome_remaining: 10,
      intl_welcome_total: 100,
    })
    expect(parsed?.policy).toBe('welcome')
  })
})
