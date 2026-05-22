/**
 * 邀请奖励分档展示（v1.1.0 · docs/01 §7 余量）
 *
 * 每 5 位「有效邀请」为一档，赠 7 天会员（与邀请页规则文案一致）。
 */

import type { InvitationItem } from '@/services/invitationService'

export const INVITE_REWARD_TIER_SIZE = 5
export const INVITE_REWARD_DAYS_PER_TIER = 7

export interface InviteRewardTier {
  tierIndex: number
  rangeLabel: string
  validItems: InvitationItem[]
  /** 本档 5 人是否已满（满则对应一次 +7 天奖励） */
  isComplete: boolean
  rewardGranted: boolean
}

export interface InviteListSections {
  tiers: InviteRewardTier[]
  pendingRegistered: InvitationItem[]
}

export function groupInvitationsByRewardTier(
  list: InvitationItem[],
  tierSize: number = INVITE_REWARD_TIER_SIZE,
): InviteListSections {
  const valid = list.filter((i) => i.status === 'valid')
  const pendingRegistered = list.filter((i) => i.status === 'registered')

  const tiers: InviteRewardTier[] = []
  const tierCount = Math.max(1, Math.ceil(valid.length / tierSize) || 0)

  for (let t = 0; t < tierCount; t += 1) {
    const slice = valid.slice(t * tierSize, (t + 1) * tierSize)
    if (slice.length === 0 && t > 0) break
    const start = t * tierSize + 1
    const end = (t + 1) * tierSize
    tiers.push({
      tierIndex: t + 1,
      rangeLabel: `第 ${t + 1} 档（有效邀请 ${start}–${end} 人）`,
      validItems: slice,
      isComplete: slice.length >= tierSize,
      rewardGranted: slice.some((i) => i.bonus_granted),
    })
  }

  if (tiers.length === 0) {
    tiers.push({
      tierIndex: 1,
      rangeLabel: `第 1 档（有效邀请 1–${tierSize} 人）`,
      validItems: [],
      isComplete: false,
      rewardGranted: false,
    })
  }

  return { tiers, pendingRegistered }
}
