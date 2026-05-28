/**
 * P2-M11-04 · 阶段考核客户端辅助（pass_criteria 解析）。
 */

import type { LessonRead } from '@/services/coursesService'

export interface EngineScorePassCriteria {
  type: 'engine_score'
  engine_mode?: string
  phase?: string
  min_score?: number
  max_attempts_per_day?: number
}

export function isAssessmentLesson(lesson: LessonRead): boolean {
  const pc = lesson.pass_criteria
  if (!pc || typeof pc !== 'object') return false
  return (pc as Record<string, unknown>).type === 'engine_score'
}

function asEngineScoreCriteria(
  passCriteria: Record<string, unknown>,
): EngineScorePassCriteria {
  return passCriteria as unknown as EngineScorePassCriteria
}

export function getAssessmentMinScore(lesson: LessonRead): number {
  const pc = asEngineScoreCriteria(lesson.pass_criteria)
  return typeof pc.min_score === 'number' ? pc.min_score : 80
}

export function getAssessmentMaxAttempts(lesson: LessonRead): number {
  const pc = asEngineScoreCriteria(lesson.pass_criteria)
  return typeof pc.max_attempts_per_day === 'number' ? pc.max_attempts_per_day : 3
}
