/**
 * M8-03 / M8-06 · 教练-学员绑定 + 学员看板 service。
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

export interface CoachDashboardStudentItem {
  student_user_id: string
  display_name: string
  avatar_url: string | null
  relation_id: string
  analyses_7d: number
  last_analysis_at: string | null
  last_annotation_at: string | null
  pending_tasks: number
  needs_response: boolean
}

export interface CoachDashboardListResponse {
  students: CoachDashboardStudentItem[]
  total: number
  cached_at: string | null
}

export interface CoachDashboardDetailResponse extends CoachDashboardStudentItem {
  recent_analyses: {
    id: string
    created_at: string
    overall_score: number | null
    club_type: string | null
    status: string
  }[]
  recent_annotations: {
    id: string
    annotation_type: string
    text_content: string | null
    created_at: string
  }[]
  pending_coach_tasks: {
    id: string
    drill_name: string | null
    target_count: number
    status: string
    created_at: string
  }[]
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
}[] = [
  { key: 'handicap', label: '差点 / 水平' },
  { key: 'goals', label: '练习目标' },
  { key: 'training_preference', label: '训练偏好' },
  { key: 'frequent_venues', label: '常去球馆' },
  { key: 'body', label: '身高体重 / 利手' },
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

  dashboardList(): Promise<CoachDashboardListResponse> {
    return http.get<CoachDashboardListResponse>('/coach/students/dashboard')
  },

  dashboardDetail(studentUserId: string): Promise<CoachDashboardDetailResponse> {
    return http.get<CoachDashboardDetailResponse>(
      `/coach/students/${encodeURIComponent(studentUserId)}/dashboard`,
    )
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
