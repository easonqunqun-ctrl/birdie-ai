/**
 * P2-M9-03 · onboarding 2.0 客户端常量（对齐 kickoff §4.3）
 *
 * 与后端枚举对齐：
 * - HANDEDNESS_OPTIONS → user_profiles_v2.handedness CHECK (right|left|switch)
 * - INJURY_OPTIONS → known_injuries JSONB 数组 + tests/test_llm_no_injury.py 白名单
 * - HANDICAP_RANGES → 自评水平 5 段（kickoff §3.3.1）
 */

export type HandednessOption = 'right' | 'left' | 'switch'
export type HandicapSource = 'rcga' | 'usga' | 'self'
export type InjuryKey =
  | 'lower_back'
  | 'shoulder'
  | 'elbow'
  | 'wrist'
  | 'knee'
  | 'hip'
  | 'neck'
  | 'other'

export interface HandicapRange {
  id: string
  label: string
  /** 上报到后端的 handicap_self 中位估值 */
  value: number
}

export interface InjuryOption {
  id: InjuryKey
  label: string
}

export interface HandednessChoice {
  id: HandednessOption
  label: string
}

export interface HandicapSourceChoice {
  id: HandicapSource
  label: string
}

export const HANDICAP_RANGES: HandicapRange[] = [
  { id: 'sub_10', label: '< 10（高手）', value: 8 },
  { id: '10_18', label: '10-18（进阶）', value: 14 },
  { id: '18_25', label: '18-25（中级）', value: 21 },
  { id: '25_36', label: '25-36（入门）', value: 30 },
  { id: '36_plus', label: '36+（新手）', value: 36 },
]

export const HANDICAP_SOURCES: HandicapSourceChoice[] = [
  { id: 'rcga', label: '中高协 (CGA)' },
  { id: 'usga', label: 'USGA' },
  { id: 'self', label: '自评' },
]

export const INJURY_OPTIONS: InjuryOption[] = [
  { id: 'lower_back', label: '腰部' },
  { id: 'shoulder', label: '肩部' },
  { id: 'elbow', label: '肘关节' },
  { id: 'wrist', label: '手腕' },
  { id: 'knee', label: '膝盖' },
  { id: 'hip', label: '髋关节' },
  { id: 'neck', label: '颈部' },
  { id: 'other', label: '其他' },
]

export const HANDEDNESS_OPTIONS: HandednessChoice[] = [
  { id: 'right', label: '右手' },
  { id: 'left', label: '左手' },
  { id: 'switch', label: '换手' },
]

export const TRAINING_PREFERENCE_OPTIONS: { id: 'video' | 'text' | 'mixed'; label: string }[] = [
  { id: 'video', label: '看视频学动作' },
  { id: 'text', label: '看文字要点' },
  { id: 'mixed', label: '图文都可以' },
]

export const WEEKLY_TARGET_OPTIONS: { value: number; label: string }[] = [
  { value: 1, label: '每周约 1 次' },
  { value: 2, label: '每周 2–3 次' },
  { value: 4, label: '每周 4 次及以上' },
  { value: 0, label: '偶尔练' },
]

/** M9-05：常去球馆上限（与 backend MAX_FAVORITE_VENUES 一致）。 */
export const MAX_FAVORITE_VENUES = 6 as const

/** Onboarding 2.0 步数（一期 3 题 → 二期 6 题）。 */
export const ONBOARDING_V2_TOTAL_STEPS = 6 as const

/**
 * 身高 / 体重默认范围（与后端 CHECK 约束一致）。
 * 客户端 UI 仅做提示性校验；最终由后端 schema 兜底。
 */
export const HEIGHT_RANGE = { min: 100, max: 250, default: 170 } as const
export const WEIGHT_RANGE = { min: 30, max: 200, default: 65 } as const
export const HANDICAP_RANGE = { min: -10, max: 54 } as const
