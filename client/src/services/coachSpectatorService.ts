/**
 * P2-M13-10 · 教练旁观学员约球 service。
 */

import { http } from './request'
import type { MeetupInvitationRead } from './meetupService'

export interface CoachSpectatorInvitationRead {
  id: string
  student_role: 'inviter' | 'invitee'
  peer_user_id: string | null
  peer_redacted: boolean
  venue_id: string | null
  proposed_time: string | null
  expires_at: string | null
  status: MeetupInvitationRead['status']
  accepted_at: string | null
  created_at: string
}

export interface CoachStudentMeetupsResponse {
  items: CoachSpectatorInvitationRead[]
  total: number
  page: number
  page_size: number
  student_user_id: string
}

export const coachSpectatorService = {
  listStudentMeetups(
    studentId: string,
    params?: { page?: number; page_size?: number },
  ): Promise<CoachStudentMeetupsResponse> {
    const q = new URLSearchParams()
    if (params?.page) q.set('page', String(params.page))
    if (params?.page_size) q.set('page_size', String(params.page_size))
    const suffix = q.toString() ? `?${q.toString()}` : ''
    return http.get<CoachStudentMeetupsResponse>(
      `/coach/students/${encodeURIComponent(studentId)}/meetups${suffix}`,
    )
  },
}
