/**
 * P2-M11-03：课程学习路径客户端 service。
 *
 * 对齐 backend/app/api/v1/courses.py (M11-02)：
 * - GET /v1/courses?stage=N
 * - GET /v1/courses/{course_id}
 * - GET /v1/courses/{course_id}/lessons
 *
 * 灰度
 * ----
 * 客户端 `PHASE2_COURSES_ENABLED_FLAG`（constants/flags.ts）；
 * 后端 `settings.PHASE2_COURSES_ENABLED`，未启用时返回 404。
 * UI 层面在调用前应自行检查 flag，避免 404 弹错误 Toast。
 */

import { http } from './request'

export interface CourseRead {
  id: string
  code: string
  title: string
  subtitle: string | null
  cover_url: string | null
  stage: number
  sort_order: number
  is_member_only: boolean
  description: string | null
  learning_objectives: string[]
  estimated_minutes: number
  created_by_user_id: string | null
  is_published: boolean
  published_at: string | null
}

export interface LessonRead {
  id: string
  course_id: string
  code: string
  title: string
  sort_order: number
  duration_minutes: number
  video_url: string | null
  transcript: string | null
  drill_ids: string[]
  pro_clip_ids: string[]
  quiz_payload: Record<string, unknown> | null
  pass_criteria: Record<string, unknown>
}

export interface CourseLessonsResponse {
  course_id: string
  items: LessonRead[]
  total: number
}

/** P2-M11-04 · POST /lessons/{id}/attempt 响应。 */
export interface CertificateDetail {
  id: string
  user_id: string
  course_id: string
  stage: number
  cert_url: string | null
  issued_at: string
  revoked_at: string | null
  course_title: string
  badge_label: string
  holder_name: string
  stage_title: string
}

export interface UserCourseStageSummary {
  current_stage: number
  earned_stages: number[]
  certificates: CertificateDetail[]
}

export interface LessonAttemptResponse {
  passed: boolean
  score: number
  min_score: number
  attempts_used: number
  max_attempts: number
  failure_reason: 'score_below_threshold' | 'engine_mode_mismatch' | null
  feedback: string
  stage_upgraded: boolean
  upgraded_to_stage: number | null
  certificate: CertificateDetail | null
}

export const coursesService = {
  list(stage?: number) {
    const path = stage != null ? `/courses?stage=${stage}` : '/courses'
    return http.get<CourseRead[]>(path)
  },
  detail(courseId: string) {
    return http.get<CourseRead>(`/courses/${courseId}`)
  },
  lessons(courseId: string) {
    return http.get<CourseLessonsResponse>(`/courses/${courseId}/lessons`)
  },
  submitLessonAttempt(lessonId: string, swingAnalysisId: string) {
    return http.post<LessonAttemptResponse>(
      `/lessons/${encodeURIComponent(lessonId)}/attempt`,
      { swing_analysis_id: swingAnalysisId },
    )
  },
  myCourseStage() {
    return http.get<UserCourseStageSummary>('/users/me/course-stage')
  },
  myCertificates() {
    return http.get<CertificateDetail[]>('/users/me/certificates')
  },
  certificateDetail(certId: string) {
    return http.get<CertificateDetail>(
      `/users/me/certificates/${encodeURIComponent(certId)}`,
    )
  },
}
