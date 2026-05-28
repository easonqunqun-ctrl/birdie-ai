/**
 * P2-M11-04 · courseAssessment 工具单测
 */

import type { LessonRead } from '@/services/coursesService'
import {
  getAssessmentMaxAttempts,
  getAssessmentMinScore,
  isAssessmentLesson,
} from '@/utils/courseAssessment'

const baseLesson = (pass_criteria: Record<string, unknown>): LessonRead => ({
  id: 'les_1',
  course_id: 'crs_1',
  code: 'L1',
  title: '测试课时',
  sort_order: 1,
  duration_minutes: 10,
  video_url: null,
  transcript: null,
  drill_ids: [],
  pro_clip_ids: [],
  quiz_payload: null,
  pass_criteria,
})

describe('courseAssessment', () => {
  test('isAssessmentLesson true when type engine_score', () => {
    expect(
      isAssessmentLesson(baseLesson({ type: 'engine_score', min_score: 80 })),
    ).toBe(true)
  })

  test('isAssessmentLesson false for empty or other types', () => {
    expect(isAssessmentLesson(baseLesson({}))).toBe(false)
    expect(isAssessmentLesson(baseLesson({ type: 'quiz' }))).toBe(false)
  })

  test('getAssessmentMinScore defaults to 80', () => {
    expect(getAssessmentMinScore(baseLesson({ type: 'engine_score' }))).toBe(80)
    expect(
      getAssessmentMinScore(baseLesson({ type: 'engine_score', min_score: 75 })),
    ).toBe(75)
  })

  test('getAssessmentMaxAttempts defaults to 3', () => {
    expect(getAssessmentMaxAttempts(baseLesson({ type: 'engine_score' }))).toBe(3)
    expect(
      getAssessmentMaxAttempts(
        baseLesson({ type: 'engine_score', max_attempts_per_day: 5 }),
      ),
    ).toBe(5)
  })
})
