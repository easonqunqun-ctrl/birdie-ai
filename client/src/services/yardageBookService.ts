/**
 * M10-03 · 个人 yardage book API
 */

import { http } from './request'

export type YardageSource = 'self' | 'inferred' | 'none'

export interface YardageBookClubItem {
  club_id: string
  club_type: string
  nickname?: string | null
  my_yards?: number | null
  std_yards?: number | null
  sample_count: number
  source: YardageSource
}

export interface YardageBookResponse {
  clubs: YardageBookClubItem[]
}

export interface YardageBookUpdateItem {
  club_id: string
  self_yardage_m?: number | null
}

export const yardageBookService = {
  getMine() {
    return http.get<YardageBookResponse>('/users/me/yardage-book')
  },
  updateMine(clubs: YardageBookUpdateItem[]) {
    return http.put<YardageBookResponse>('/users/me/yardage-book', { clubs })
  },
}
