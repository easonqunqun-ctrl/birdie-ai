/**
 * P2-M12-10 · 职业镜头收藏 / 想试试看。
 *
 * - POST/DELETE/GET /v1/users/me/pros/favorites
 * - POST /v1/users/me/pros/favorites/{clip_id}/try-it
 */

import { http } from './request'
import type { ProPlayerRead, ProSwingClipRead } from './prosService'

export interface ProFavoriteItemRead {
  clip_id: string
  note: string | null
  training_task_id: string | null
  created_at: string
  clip: ProSwingClipRead
  player: ProPlayerRead
  clip_unavailable: boolean
}

export interface ProTryItResponse {
  training_task_id: string
  created: boolean
}

export interface ProFavoriteCreate {
  clip_id: string
  note?: string | null
}

export const proFavoritesService = {
  list() {
    return http.get<ProFavoriteItemRead[]>('/users/me/pros/favorites')
  },
  add(body: ProFavoriteCreate) {
    return http.post<ProFavoriteItemRead>('/users/me/pros/favorites', body)
  },
  remove(clipId: string) {
    return http.del<Record<string, never>>(`/users/me/pros/favorites/${clipId}`)
  },
  tryIt(clipId: string) {
    return http.post<ProTryItResponse>(`/users/me/pros/favorites/${clipId}/try-it`, {})
  },
}
