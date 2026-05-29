/**
 * P2-M12-03：球手对比库客户端 service。
 *
 * 对齐 backend/app/api/v1/pros.py (M12-02)：
 * - GET /v1/pros
 * - GET /v1/pros/{player_id}
 * - GET /v1/pros/{player_id}/clips?camera_angle=&club_type=
 * - GET /v1/analyses/{analysis_id}/pro-matches?limit=&record=  （M12-04）
 *
 * 灰度
 * ----
 * `PHASE2_PROS_ENABLED_FLAG`（constants/flags.ts）；后端同名 `PHASE2_PROS_ENABLED`。
 */

import { http } from './request'

export type ProCameraAngle = 'face_on' | 'down_the_line'
export type ProLicenseStatus = 'public_clip' | 'authorized' | 'partnership'
export type ProHandedness = 'right' | 'left'

export interface ProPlayerRead {
  id: string
  name: string
  name_en: string | null
  nationality: string | null
  handedness: ProHandedness
  height_cm: number | null
  avatar_url: string | null
  short_bio: string | null
  license_status: ProLicenseStatus
  is_active: boolean
  sort_order: number
}

export interface ProSwingClipRead {
  id: string
  pro_player_id: string
  club_type: string
  camera_angle: ProCameraAngle
  video_url: string
  thumbnail_url: string | null
  duration_ms: number | null
  fps: number | null
  overall_score: number | null
  engine_version: string
  features_snapshot: Record<string, unknown>
  license_status: ProLicenseStatus
  source_credit: string
  source_url: string
  captured_year: number | null
  is_published: boolean
}

export interface ListClipsQuery {
  camera_angle?: ProCameraAngle
  club_type?: string
}

export interface ProMatchItemRead {
  match_score: number
  match_details: Record<string, unknown>
  clip: ProSwingClipRead
  player: ProPlayerRead
}

export interface ProMatchResultRead {
  analysis_id: string
  matches: ProMatchItemRead[]
  recorded_match_id: string | null
}

export interface ProMatchQuery {
  limit?: number
  record?: boolean
}

export const prosService = {
  list() {
    return http.get<ProPlayerRead[]>('/pros')
  },
  detail(playerId: string) {
    return http.get<ProPlayerRead>(`/pros/${playerId}`)
  },
  clips(playerId: string, query: ListClipsQuery = {}) {
    const qs: string[] = []
    if (query.camera_angle) qs.push(`camera_angle=${query.camera_angle}`)
    if (query.club_type) qs.push(`club_type=${encodeURIComponent(query.club_type)}`)
    const tail = qs.length ? `?${qs.join('&')}` : ''
    return http.get<ProSwingClipRead[]>(`/pros/${playerId}/clips${tail}`)
  },
  matchForAnalysis(analysisId: string, query: ProMatchQuery = {}) {
    const qs: string[] = []
    if (query.limit != null) qs.push(`limit=${query.limit}`)
    if (query.record != null) qs.push(`record=${query.record ? 'true' : 'false'}`)
    const tail = qs.length ? `?${qs.join('&')}` : ''
    return http.get<ProMatchResultRead>(`/analyses/${analysisId}/pro-matches${tail}`)
  },
}
