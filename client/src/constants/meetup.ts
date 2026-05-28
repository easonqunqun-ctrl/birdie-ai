/**
 * P2-M13-05 · 约球客户端常量（对齐 backend/schemas/meetup.py）
 */

export type InvitationStatus =
  | 'pending'
  | 'accepted'
  | 'declined'
  | 'expired'
  | 'cancelled'

export type MeetupListRole = 'any' | 'inviter' | 'invitee'

export type VenueType =
  | 'indoor_range'
  | 'outdoor_range'
  | 'simulator_lounge'
  | 'golf_course'

export const INVITATION_STATUS_LABEL: Record<InvitationStatus, string> = {
  pending: '待回复',
  accepted: '已接受',
  declined: '已拒绝',
  expired: '已过期',
  cancelled: '已撤回',
}

export const MEETUP_ROLE_TAB: { key: MeetupListRole; label: string }[] = [
  { key: 'any', label: '全部' },
  { key: 'invitee', label: '收到的' },
  { key: 'inviter', label: '发出的' },
]

export const VENUE_TYPE_LABEL: Record<VenueType, string> = {
  indoor_range: '室内练习场',
  outdoor_range: '室外练习场',
  simulator_lounge: '模拟器',
  golf_course: '球场',
}
