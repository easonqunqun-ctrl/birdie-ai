/**
 * 高尔夫档案的选项常量。
 *
 * 由「新用户引导 onboarding」与「我的 · 编辑档案」共用，
 * 保证两处的字面量、排序、展示文案完全一致。
 */

import type { GolfLevel, PrimaryGoal, WeeklyFreq } from '@/types/api'

export interface LevelOption {
  value: GolfLevel
  label: string
  desc: string
}

export interface GoalOption {
  value: PrimaryGoal
  label: string
}

export interface FreqOption {
  value: WeeklyFreq
  label: string
}

export const LEVELS: readonly LevelOption[] = [
  { value: 'beginner', label: '初学者', desc: '刚接触不到 1 年' },
  { value: 'elementary', label: '初级', desc: '1-3 年，差点 25+' },
  { value: 'intermediate', label: '中级', desc: '差点 10-25' },
  { value: 'advanced', label: '高级', desc: '差点 10 以下' }
]

export const GOALS: readonly GoalOption[] = [
  { value: 'distance', label: '提升距离' },
  { value: 'accuracy', label: '提升准度' },
  { value: 'short_game', label: '短杆球技' },
  { value: 'putting', label: '推杆技术' },
  { value: 'consistency', label: '一致性' }
]

export const FREQS: readonly FreqOption[] = [
  { value: 'occasional', label: '偶尔' },
  { value: 'once', label: '每周 1 次' },
  { value: 'frequent', label: '每周 2-3 次' },
  { value: 'daily', label: '几乎每天' }
]

/** 一次性的 value→label 映射，方便「我的」页等只读展示场景 */
export const LEVEL_LABEL: Record<GolfLevel, string> = Object.fromEntries(
  LEVELS.map((l) => [l.value, l.label])
) as Record<GolfLevel, string>

export const GOAL_LABEL: Record<PrimaryGoal, string> = Object.fromEntries(
  GOALS.map((g) => [g.value, g.label])
) as Record<PrimaryGoal, string>

export const FREQ_LABEL: Record<WeeklyFreq, string> = Object.fromEntries(
  FREQS.map((f) => [f.value, f.label])
) as Record<WeeklyFreq, string>

/** 目标上限（与后端 schema 的 max_length 对齐） */
export const MAX_GOALS = 3
