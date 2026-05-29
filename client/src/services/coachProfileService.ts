/**
 * P2-M8-01 · 教练档案 / 资质申请 service。
 */

import { http } from './request'

export type CoachLevel = 'pga' | 'china_pga' | 'regional' | 'club_pro'
export type CoachProfileStatus = 'pending' | 'active' | 'rejected' | 'paused'

export interface CoachProfileBrief {
  status: CoachProfileStatus
  display_name: string
  level: CoachLevel
  applied_at: string
  approved_at: string | null
  rejected_at: string | null
}

export interface CoachProfileRead extends CoachProfileBrief {
  user_id: string
  avatar_url: string | null
  bio: string | null
  specialties: string[]
  service_cities: string[]
  certifications: Record<string, unknown>[]
  latest_verification_id: string | null
  latest_review_status: string | null
}

export interface CoachProfileApplyPayload {
  display_name: string
  level: CoachLevel
  bio?: string
  avatar_url?: string
  specialties?: string[]
  service_cities?: string[]
  certifications?: Record<string, unknown>[]
  materials?: { type: string; object_key: string }[]
}

export const COACH_LEVEL_OPTIONS: { value: CoachLevel; label: string }[] = [
  { value: 'pga', label: 'PGA 认证' },
  { value: 'china_pga', label: '中高协教练' },
  { value: 'regional', label: '地方协会' },
  { value: 'club_pro', label: '球会职业' },
]

export const coachProfileService = {
  apply(payload: CoachProfileApplyPayload): Promise<CoachProfileRead> {
    return http.post<CoachProfileRead>('/coach/profile/apply', payload)
  },

  me(): Promise<CoachProfileRead | null> {
    return http.get<CoachProfileRead | null>('/coach/profile/me')
  },
}
