/**
 * P2-M13-08 · 自助挑战赛 service。
 */

import { http } from './request'

export type MeetupEventTemplateCode =
  | 'putting_contest'
  | 'distance_contest'
  | 'overall_score'

export interface MeetupEventTemplate {
  code: MeetupEventTemplateCode
  label: string
  description: string
  default_capacity: number
  score_label: string
}

export interface MeetupEventLeaderboardItem {
  rank: number
  user_id: string
  participation_id: string
  self_reported_score: number
  submitted_at: string | null
}

export interface MeetupEventRead {
  id: string
  organizer_user_id: string
  venue_id: string | null
  title: string
  description: string | null
  template_code: MeetupEventTemplateCode | null
  template_label: string | null
  scheduled_at: string | null
  capacity: number | null
  participant_count: number
  status: string
  badge_template_code: string | null
  rules_payload: Record<string, unknown>
  score_label: string | null
  my_completion_badge: Record<string, unknown> | null
  my_participation_status: string | null
  leaderboard: MeetupEventLeaderboardItem[]
}

export interface MeetupEventListResponse {
  items: MeetupEventRead[]
  total: number
  page: number
  page_size: number
}

export interface MeetupEventCreate {
  title: string
  template_code: MeetupEventTemplateCode
  description?: string | null
  venue_id?: string | null
  scheduled_at?: string | null
  capacity?: number | null
}

export interface MeetupEventScoreSubmit {
  self_reported_score: number
  score_image_url?: string | null
}

export const meetupEventService = {
  listTemplates(): Promise<MeetupEventTemplate[]> {
    return http.get<MeetupEventTemplate[]>('/meetups/events/templates')
  },

  create(payload: MeetupEventCreate): Promise<MeetupEventRead> {
    return http.post<MeetupEventRead>('/meetups/events', payload)
  },

  list(params?: { page?: number; page_size?: number; status?: string }): Promise<MeetupEventListResponse> {
    const qs: string[] = []
    if (params?.page != null) qs.push(`page=${params.page}`)
    if (params?.page_size != null) qs.push(`page_size=${params.page_size}`)
    if (params?.status) qs.push(`status=${encodeURIComponent(params.status)}`)
    const tail = qs.length ? `?${qs.join('&')}` : ''
    return http.get<MeetupEventListResponse>(`/meetups/events${tail}`)
  },

  get(eventId: string): Promise<MeetupEventRead> {
    return http.get<MeetupEventRead>(`/meetups/events/${encodeURIComponent(eventId)}`)
  },

  join(eventId: string): Promise<MeetupEventRead> {
    return http.post<MeetupEventRead>(`/meetups/events/${encodeURIComponent(eventId)}/join`)
  },

  submitScore(eventId: string, payload: MeetupEventScoreSubmit): Promise<MeetupEventRead> {
    return http.post<MeetupEventRead>(
      `/meetups/events/${encodeURIComponent(eventId)}/submit-score`,
      payload
    )
  },
}
