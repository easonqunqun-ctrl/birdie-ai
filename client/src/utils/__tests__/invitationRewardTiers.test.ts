import {
  groupInvitationsByRewardTier,
  INVITE_REWARD_TIER_SIZE,
} from '../invitationRewardTiers'
import type { InvitationItem } from '@/services/invitationService'

const item = (overrides: Partial<InvitationItem> & Pick<InvitationItem, 'id' | 'status'>): InvitationItem => ({
  id: overrides.id,
  invitee_id: overrides.invitee_id ?? 'u1',
  invitee_nickname_masked: overrides.invitee_nickname_masked ?? '球*友',
  status: overrides.status,
  bonus_granted: overrides.bonus_granted ?? false,
  bonus_granted_at: overrides.bonus_granted_at ?? null,
  created_at: overrides.created_at ?? '2026-05-01T00:00:00Z',
})

describe('invitationRewardTiers', () => {
  it('空列表仍有一档占位', () => {
    const { tiers, pendingRegistered } = groupInvitationsByRewardTier([])
    expect(tiers).toHaveLength(1)
    expect(tiers[0].validItems).toHaveLength(0)
    expect(pendingRegistered).toHaveLength(0)
  })

  it('6 位有效邀请拆成两档', () => {
    const list = Array.from({ length: 6 }, (_, i) =>
      item({ id: String(i), status: 'valid', bonus_granted: i < 5 }),
    )
    const { tiers } = groupInvitationsByRewardTier(list)
    expect(tiers).toHaveLength(2)
    expect(tiers[0].validItems).toHaveLength(INVITE_REWARD_TIER_SIZE)
    expect(tiers[0].isComplete).toBe(true)
    expect(tiers[1].validItems).toHaveLength(1)
  })

  it('registered 归入 pendingRegistered', () => {
    const { pendingRegistered } = groupInvitationsByRewardTier([
      item({ id: '1', status: 'registered' }),
    ])
    expect(pendingRegistered).toHaveLength(1)
  })
})
