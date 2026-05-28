/**
 * P2-M9-03 · 画像 2.0 客户端 service。
 *
 * 对应 docs/02 §11.3：
 * - GET  /v1/users/me/profile-v2
 * - PUT  /v1/users/me/profile-v2 （PATCH 语义，仅更新请求体内字段；null/[] 触发清空）
 *
 * 注意
 * ----
 * - consent 字段由 **后端自动推断**（kickoff §4.2 + profile_v2_consent helper）；
 *   客户端默认**不传** `privacy_payload`；如需强制开关，传 `privacy_payload`
 *   会覆盖自动推断结果。
 * - 已知伤病字段（`known_injuries`）属高敏感，UI 层必须按 §3.3.3 做二次 Modal 确认。
 */

import type {
  HandednessOption,
  HandicapSource,
  InjuryKey,
} from '@/constants/profileV2'
import type { VenueType } from '@/constants/meetup'
import { http } from './request'

export interface ProfileV2PrivacyPayload {
  handicap_consent: boolean
  body_consent: boolean
  injury_consent: boolean
  location_consent: boolean
  coach_visible_consent: boolean
}

export interface ProfileV2Read {
  user_id: string
  handicap_official: number | null
  handicap_self: number | null
  handicap_source: HandicapSource | null
  height_cm: number | null
  weight_kg: number | null
  handedness: HandednessOption | null
  known_injuries: InjuryKey[]
  mid_long_goals: string[]
  training_preference: 'video' | 'text' | 'mixed' | null
  weekly_target_sessions: number | null
  favorite_course_ids: string[]
  privacy_payload: ProfileV2PrivacyPayload
  coach_visible_fields: string[]
}

/** PATCH payload；所有字段可选，缺省视为"未更新"；显式 null/[] 视为"清空"。 */
export interface ProfileV2UpdatePayload {
  handicap_official?: number | null
  handicap_self?: number | null
  handicap_source?: HandicapSource | null
  height_cm?: number | null
  weight_kg?: number | null
  handedness?: HandednessOption | null
  known_injuries?: InjuryKey[] | null
  mid_long_goals?: string[] | null
  training_preference?: 'video' | 'text' | 'mixed' | null
  weekly_target_sessions?: number | null
  favorite_course_ids?: string[] | null
  coach_visible_fields?: string[] | null
  /** 显式 consent 控制；缺省时后端按字段值自动推断。 */
  privacy_payload?: Partial<ProfileV2PrivacyPayload>
}

/** M9-05 · GET /users/me/profile-v2/favorite-venues 列表元素。 */
export interface FavoriteVenueRead {
  id: string
  city: string
  name: string
  venue_type: VenueType
  source: 'ugc' | 'verified'
}

export interface FavoriteVenuesList {
  items: FavoriteVenueRead[]
  missing_ids: string[]
  total: number
}

export const profileV2Service = {
  get() {
    return http.get<ProfileV2Read>('/users/me/profile-v2')
  },
  update(payload: ProfileV2UpdatePayload) {
    return http.put<ProfileV2Read>('/users/me/profile-v2', payload)
  },
  listFavoriteVenues() {
    return http.get<FavoriteVenuesList>('/users/me/profile-v2/favorite-venues')
  },
}
