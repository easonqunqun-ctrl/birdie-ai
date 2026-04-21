import { http } from './request'

/** 邀请裂变相关类型（对齐 backend/app/schemas/invitation.py）. */
export type InvitationStatus = 'registered' | 'valid'

export interface InvitationItem {
  id: string
  invitee_id: string
  invitee_nickname_masked: string
  status: InvitationStatus
  bonus_granted: boolean
  bonus_granted_at: string | null
  created_at: string
}

export interface InviteInfo {
  invite_code: string
  total_invited: number
  valid_count: number
  next_reward_at: number
  days_to_next_reward: number
  total_bonus_days: number
}

export const invitationService = {
  getInfo() {
    return http.get<InviteInfo>('/users/me/invite-info')
  },
  listInvitations() {
    return http.get<InvitationItem[]>('/users/me/invitations')
  }
}
