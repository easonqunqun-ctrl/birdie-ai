/**
 * M8-03 · 教练-学员双向 opt-in 绑定 service。
 */

import { http } from './request'

export type CoachStudentStatus = 'pending' | 'active' | 'paused' | 'ended'

export interface CoachStudentUserBrief {
  user_id: string
  nickname: string | null
  display_name?: string | null
}

export interface CoachStudentRelationRead {
  id: string
  coach_user_id: string
  student_user_id: string
  status: CoachStudentStatus
  visibility_payload: Record<string, boolean>
  invited_at: string
  invite_message?: string | null
  accepted_at?: string | null
  ended_at?: string | null
  coach?: CoachStudentUserBrief | null
  student?: CoachStudentUserBrief | null
}

export interface StudentCoachOverview {
  pending: CoachStudentRelationRead[]
  active: CoachStudentRelationRead | null
  paused: CoachStudentRelationRead | null
}

export interface CoachStudentVisibilityUpdate {
  handicap?: boolean
  body?: boolean
  injuries?: boolean
  goals?: boolean
  training_preference?: boolean
  frequent_venues?: boolean
}

export const COACH_VISIBILITY_FIELDS: {
  key: keyof CoachStudentVisibilityUpdate
  label: string
  sensitive?: boolean
}[] = [
  { key: 'handicap', label: '差点 / 水平' },
  { key: 'goals', label: '练习目标' },
  { key: 'training_preference', label: '训练偏好' },
  { key: 'frequent_venues', label: '常去球馆' },
  { key: 'body', label: '身高体重' },
  { key: 'injuries', label: '伤病信息', sensitive: true },
]

export const coachStudentsService = {
  invite(payload: {
    student_user_id?: string
    invite_code?: string
    message?: string
  }): Promise<CoachStudentRelationRead> {
    return http.post<CoachStudentRelationRead>('/coach/students/invite', payload)
  },

  list(status?: CoachStudentStatus): Promise<{ items: CoachStudentRelationRead[]; total: number }> {
    const qs = status ? `?status=${encodeURIComponent(status)}` : ''
    return http.get(`/coach/students${qs}`)
  },

  endAsCoach(relationId: string): Promise<CoachStudentRelationRead> {
    return http.post<CoachStudentRelationRead>(
      `/coach/students/${encodeURIComponent(relationId)}/end`,
      {},
    )
  },

  myCoachOverview(): Promise<StudentCoachOverview> {
    return http.get<StudentCoachOverview>('/users/me/coach')
  },

  accept(relationId: string): Promise<CoachStudentRelationRead> {
    return http.post<CoachStudentRelationRead>(
      `/users/me/coach/${encodeURIComponent(relationId)}/accept`,
      {},
    )
  },

  reject(relationId: string): Promise<CoachStudentRelationRead> {
    return http.post<CoachStudentRelationRead>(
      `/users/me/coach/${encodeURIComponent(relationId)}/reject`,
      {},
    )
  },

  endAsStudent(relationId: string): Promise<CoachStudentRelationRead> {
    return http.post<CoachStudentRelationRead>(
      `/users/me/coach/${encodeURIComponent(relationId)}/end`,
      {},
    )
  },

  updateVisibility(
    relationId: string,
    payload: CoachStudentVisibilityUpdate,
  ): Promise<CoachStudentRelationRead> {
    return http.put<CoachStudentRelationRead>(
      `/users/me/coach/${encodeURIComponent(relationId)}/visibility`,
      payload,
    )
  },
}
