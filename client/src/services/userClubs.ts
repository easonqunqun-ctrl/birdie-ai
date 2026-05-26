/**
 * P2-M9-02：装备清单 CRUD 客户端服务。
 *
 * 与 backend/app/api/v1/users.py /me/clubs* 对齐；与 schemas/user_club.py 字段一致。
 *
 * 灰度开关：客户端 `PHASE2_PROFILE_V2_ENABLED_FLAG`（constants/flags.ts）；
 * 后端 `settings.PHASE2_PROFILE_V2_ENABLED`，未启用时 API 返回 404。
 */

import { http } from './request'
import type { ClubType } from '@/types/api'

export interface UserClub {
  id: string
  club_type: ClubType
  nickname: string | null
  self_yardage_m: number | null
  is_active: boolean
  sort_order: number
  created_at: string
  updated_at: string
}

export interface UserClubListResponse {
  items: UserClub[]
  total: number
  max_clubs: number
  remaining: number
}

export interface UserClubCreateRequest {
  club_type: ClubType
  nickname?: string | null
  self_yardage_m?: number | null
  is_active?: boolean
  sort_order?: number
}

export type UserClubUpdateRequest = Partial<UserClubCreateRequest>

export const userClubsService = {
  list() {
    return http.get<UserClubListResponse>('/users/me/clubs')
  },

  create(payload: UserClubCreateRequest) {
    return http.post<UserClub>('/users/me/clubs', payload)
  },

  update(clubId: string, payload: UserClubUpdateRequest) {
    return http.put<UserClub>(`/users/me/clubs/${clubId}`, payload)
  },

  remove(clubId: string) {
    return http.del<{ id: string; deleted: boolean }>(`/users/me/clubs/${clubId}`)
  },
}
