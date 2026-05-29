/**
 * P2-M13-07 · 约球互评 API 客户端。
 */

import { http } from './request'

export interface MeetupFeedbackRead {
  id: string
  invitation_id: string
  reviewer_user_id: string
  reviewee_user_id: string
  rating: number
  tags: string[]
  credit_delta: number
  comment: string | null
  is_visible: boolean
  created_at: string
}

export interface MeetupFeedbackListResponse {
  items: MeetupFeedbackRead[]
  total: number
  invitation_id?: string | null
}

export interface MeetupFeedbackEligibility {
  can_submit: boolean
  opens_at: string | null
  has_submitted: boolean
  peer_visible: boolean
}

export interface MeetupFeedbackSubmit {
  invitation_id: string
  rating: number
  tags: string[]
  comment?: string | null
}

export const MEETUP_FEEDBACK_TAG_OPTIONS = [
  { key: 'on_time', label: '守时' },
  { key: 'friendly', label: '友好' },
  { key: 'patient_teaching', label: '教学耐心' },
  { key: 'no_show', label: '失约' },
  { key: 'rude', label: '言语不当' },
] as const

export const meetupFeedbackService = {
  submit(payload: MeetupFeedbackSubmit) {
    return http.post<MeetupFeedbackRead>('/meetups/feedbacks', payload)
  },
  listForInvitation(invitationId: string) {
    return http.get<MeetupFeedbackListResponse>(
      `/meetups/feedbacks?invitation_id=${encodeURIComponent(invitationId)}`,
    )
  },
  eligibility(invitationId: string) {
    return http.get<MeetupFeedbackEligibility>(
      `/meetups/feedbacks/eligibility?invitation_id=${encodeURIComponent(invitationId)}`,
    )
  },
  listMine(limit = 50) {
    return http.get<MeetupFeedbackListResponse>(
      `/users/me/meetup-feedbacks?limit=${limit}`,
    )
  },
}
