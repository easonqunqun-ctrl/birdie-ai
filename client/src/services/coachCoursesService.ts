/**
 * P2-M11-06 · 教练定制课程写端点客户端 service。
 *
 * 需后端 `PHASE2_COURSES_ENABLED` + 用户 ID 在 `COACH_COURSE_USER_IDS` 白名单。
 * 教练端 UI 挂 M8（wait-for-triggers §2.16）。
 */

import { http } from './request'
import type { CourseRead, LessonRead } from './coursesService'

export interface CoachCourseDetailResponse {
  course: CourseRead
  lessons: LessonRead[]
}

export interface CoachCourseCreatePayload {
  code?: string
  title: string
  subtitle?: string | null
  cover_url?: string | null
  stage: number
  sort_order?: number
  is_member_only?: boolean
  description?: string | null
  learning_objectives?: string[]
  estimated_minutes?: number
}

export interface CoachCourseUpdatePayload {
  title?: string
  subtitle?: string | null
  cover_url?: string | null
  sort_order?: number
  is_member_only?: boolean
  description?: string | null
  learning_objectives?: string[]
  estimated_minutes?: number
}

export interface CoachLessonCreatePayload {
  code: string
  title: string
  sort_order: number
  duration_minutes?: number
  video_url?: string | null
  transcript?: string | null
  drill_ids?: string[]
  pro_clip_ids?: string[]
  quiz_payload?: Record<string, unknown> | null
  pass_criteria?: Record<string, unknown>
}

export const coachCoursesService = {
  listMine() {
    return http.get<CourseRead[]>('/users/me/coach/courses')
  },
  getDetail(courseId: string) {
    return http.get<CoachCourseDetailResponse>(
      `/users/me/coach/courses/${encodeURIComponent(courseId)}`,
    )
  },
  create(payload: CoachCourseCreatePayload) {
    return http.post<CourseRead>('/users/me/coach/courses', payload)
  },
  update(courseId: string, payload: CoachCourseUpdatePayload) {
    return http.patch<CourseRead>(
      `/users/me/coach/courses/${encodeURIComponent(courseId)}`,
      payload,
    )
  },
  addLesson(courseId: string, payload: CoachLessonCreatePayload) {
    return http.post<LessonRead>(
      `/users/me/coach/courses/${encodeURIComponent(courseId)}/lessons`,
      payload,
    )
  },
  publish(courseId: string) {
    return http.post<CourseRead>(
      `/users/me/coach/courses/${encodeURIComponent(courseId)}/publish`,
      {},
    )
  },
  unpublish(courseId: string) {
    return http.post<CourseRead>(
      `/users/me/coach/courses/${encodeURIComponent(courseId)}/unpublish`,
      {},
    )
  },
}
