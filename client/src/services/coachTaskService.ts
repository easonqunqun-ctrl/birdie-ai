/**
 * M8-05 · 教练作业派发 API。
 */

import { http } from './request'

export type CoachAssignedStatus = 'assigned' | 'started' | 'done' | 'expired'

export interface CoachAssignedTaskRead {
  id: string
  coach_user_id: string
  student_user_id: string
  relation_id: string
  source_type: 'drill' | 'custom_video'
  drill_id: string | null
  target_week: string
  target_count: number
  target_issue: string | null
  coach_note: string | null
  training_task_id: string | null
  status: CoachAssignedStatus
  completed_at: string | null
  created_at: string
  student?: { id: string; nickname: string | null }
  drill?: { id: string; name: string }
}

export interface CoachTaskAssignRequest {
  student_user_id: string
  source_type: 'drill'
  drill_id: string
  target_week: string
  target_count: number
  target_issue?: string
  coach_note?: string
}

export const coachTaskService = {
  assign(body: CoachTaskAssignRequest) {
    return http.post<CoachAssignedTaskRead>('/coach/tasks/assign', body)
  },
  list(params?: { studentId?: string; status?: CoachAssignedStatus }) {
    const query = new URLSearchParams()
    if (params?.studentId) query.set('student_id', params.studentId)
    if (params?.status) query.set('status', params.status)
    const suffix = query.toString()
    return http.get<{ items: CoachAssignedTaskRead[]; total: number }>(
      `/coach/tasks${suffix ? `?${suffix}` : ''}`,
    )
  },
}
