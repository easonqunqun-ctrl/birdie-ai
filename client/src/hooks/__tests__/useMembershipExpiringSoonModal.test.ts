/**
 * `useMembershipExpiringSoonModal` 纯函数 + hook 单测.
 *
 * 重点验证：
 * - 时区无关：`toShanghaiDateKey` 在 jest 跑 UTC 时也能输出上海日历日
 * - 触发窗口 [1, 7] 边界条件
 * - 自动续费 / free / null / 已过期 用户不弹
 * - localStorage 去重：同一 expire_date 第二次不重弹
 */

import {
  daysBetweenDateKeys,
  MAX_WINDOW_DAYS,
  MIN_WINDOW_DAYS,
  shouldShowExpiringSoonModal,
  toShanghaiDateKey,
} from '@/hooks/useMembershipExpiringSoonModal'
import type { MembershipInfo } from '@/types/payment'

const baseMember: MembershipInfo = {
  is_member: true,
  membership_type: 'monthly',
  expires_at: '2026-05-25T10:00:00+08:00',
  days_remaining: 5,
  auto_renew: false,
}

describe('toShanghaiDateKey', () => {
  it('UTC 17:00 应该返回次日的上海日期', () => {
    // 2026-05-20 17:00:00 UTC = 2026-05-21 01:00 上海
    const ms = Date.UTC(2026, 4, 20, 17, 0, 0)
    expect(toShanghaiDateKey(ms)).toBe('2026-05-21')
  })

  it('UTC 00:00 应该返回当日的上海日期（+8h 内不跨日）', () => {
    const ms = Date.UTC(2026, 4, 20, 0, 0, 0)
    expect(toShanghaiDateKey(ms)).toBe('2026-05-20')
  })
})

describe('daysBetweenDateKeys', () => {
  it('正向计数', () => {
    expect(daysBetweenDateKeys('2026-05-20', '2026-05-25')).toBe(5)
  })
  it('同日为 0', () => {
    expect(daysBetweenDateKeys('2026-05-20', '2026-05-20')).toBe(0)
  })
  it('倒序为负', () => {
    expect(daysBetweenDateKeys('2026-05-25', '2026-05-20')).toBe(-5)
  })
})

describe('shouldShowExpiringSoonModal', () => {
  const nowMs = Date.parse('2026-05-20T02:00:00+08:00')
  const todayKey = '2026-05-20'

  it('剩余 5 天且未弹过 → show=true', () => {
    const r = shouldShowExpiringSoonModal({
      membership: baseMember,
      nowMs,
      todayDateKey: todayKey,
      shownKeys: new Set(),
    })
    expect(r.show).toBe(true)
    expect(r.daysLeft).toBe(5)
    expect(r.expireDate).toBe('2026-05-25')
    expect(r.dedupKey).toBe('2026-05-25')
  })

  it('剩余 1 天（窗口下限）仍弹', () => {
    const r = shouldShowExpiringSoonModal({
      membership: { ...baseMember, expires_at: '2026-05-21T10:00:00+08:00' },
      nowMs,
      todayDateKey: todayKey,
      shownKeys: new Set(),
    })
    expect(r.show).toBe(true)
    expect(r.daysLeft).toBe(MIN_WINDOW_DAYS)
  })

  it('剩余 7 天（窗口上限）仍弹', () => {
    const r = shouldShowExpiringSoonModal({
      membership: { ...baseMember, expires_at: '2026-05-27T10:00:00+08:00' },
      nowMs,
      todayDateKey: todayKey,
      shownKeys: new Set(),
    })
    expect(r.show).toBe(true)
    expect(r.daysLeft).toBe(MAX_WINDOW_DAYS)
  })

  it('剩余 8 天（超上限）不弹', () => {
    const r = shouldShowExpiringSoonModal({
      membership: { ...baseMember, expires_at: '2026-05-28T10:00:00+08:00' },
      nowMs,
      todayDateKey: todayKey,
      shownKeys: new Set(),
    })
    expect(r.show).toBe(false)
    expect(r.daysLeft).toBe(8)
  })

  it('剩余 0 天（含已过期）不弹（由 §1.4.2 已过期通知接管）', () => {
    const r = shouldShowExpiringSoonModal({
      membership: { ...baseMember, expires_at: '2026-05-19T10:00:00+08:00' },
      nowMs,
      todayDateKey: todayKey,
      shownKeys: new Set(),
    })
    expect(r.show).toBe(false)
  })

  it('自动续费用户不打扰', () => {
    const r = shouldShowExpiringSoonModal({
      membership: { ...baseMember, auto_renew: true },
      nowMs,
      todayDateKey: todayKey,
      shownKeys: new Set(),
    })
    expect(r.show).toBe(false)
  })

  it('free 用户不弹', () => {
    const r = shouldShowExpiringSoonModal({
      membership: { ...baseMember, membership_type: 'free', is_member: false },
      nowMs,
      todayDateKey: todayKey,
      shownKeys: new Set(),
    })
    expect(r.show).toBe(false)
  })

  it('membership=null 不弹', () => {
    const r = shouldShowExpiringSoonModal({
      membership: null,
      nowMs,
      todayDateKey: todayKey,
      shownKeys: new Set(),
    })
    expect(r.show).toBe(false)
  })

  it('已弹过同一 expire_date 不再弹（去重生效）', () => {
    const r = shouldShowExpiringSoonModal({
      membership: baseMember,
      nowMs,
      todayDateKey: todayKey,
      shownKeys: new Set(['2026-05-25']),
    })
    expect(r.show).toBe(false)
    expect(r.dedupKey).toBe('2026-05-25')
  })

  it('expires_at 解析失败安全降级', () => {
    const r = shouldShowExpiringSoonModal({
      membership: { ...baseMember, expires_at: 'not-a-date' },
      nowMs,
      todayDateKey: todayKey,
      shownKeys: new Set(),
    })
    expect(r.show).toBe(false)
  })

  it('expires_at=null 不弹', () => {
    const r = shouldShowExpiringSoonModal({
      membership: { ...baseMember, expires_at: null },
      nowMs,
      todayDateKey: todayKey,
      shownKeys: new Set(),
    })
    expect(r.show).toBe(false)
  })
})
