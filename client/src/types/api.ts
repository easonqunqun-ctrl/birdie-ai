/**
 * 与后端 API 对齐的核心类型（与 docs/02-API接口设计文档.md 保持一致）
 */

export type GolfLevel = 'beginner' | 'elementary' | 'intermediate' | 'advanced'
export type WeeklyFreq = 'occasional' | 'once' | 'frequent' | 'daily'
export type PrimaryGoal = 'distance' | 'accuracy' | 'short_game' | 'putting' | 'consistency'
export type MembershipType = 'free' | 'monthly' | 'yearly' | 'family'
export type CameraAngle = 'face_on' | 'down_the_line'
export type ClubType =
  | 'driver' | 'fairway_wood'
  | 'iron_3' | 'iron_4' | 'iron_5' | 'iron_6' | 'iron_7' | 'iron_8' | 'iron_9'
  | 'wedge' | 'putter' | 'unknown'

export type AnalysisStatus = 'pending' | 'processing' | 'completed' | 'failed'
export type AnalysisStage =
  | 'preprocessing' | 'pose_estimating' | 'phase_segmenting'
  | 'scoring' | 'diagnosing' | 'generating' | 'completed' | 'failed'

/* ==================== 通用响应 ==================== */
export interface APIResponse<T = unknown> {
  code: number
  message: string
  data?: T
  detail?: string
}

export interface PageData<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  has_more: boolean
}

/* ==================== 用户 ==================== */
export interface UserStats {
  total_analyses: number
  total_practices: number
  streak_days: number
  best_score: number
  score_improvement: number
}

export interface UserQuota {
  analysis_remaining: number
  analysis_total: number
  analysis_reset_at: string | null
  chat_remaining_today: number
  chat_total_today: number
}

export interface User {
  id: string
  nickname: string | null
  avatar_url: string | null
  golf_level: GolfLevel | null
  primary_goals: string[]
  weekly_practice_frequency: WeeklyFreq | null
  membership_type: MembershipType
  membership_expires_at: string | null
  /** W7-T1：后端派生字段，前端不必再计算时区偏差 */
  is_member: boolean
  /** W7-T1：会员剩余天数；非会员为 0 */
  membership_days_remaining: number
  onboarding_completed: boolean
  stats?: UserStats
  quota?: UserQuota
  created_at: string
}

export interface WechatLoginRequest {
  code: string
  invite_code?: string
}

export interface WechatLoginResponse {
  token: string
  expires_in: number
  is_new_user: boolean
  user: User
}

export interface OnboardingRequest {
  golf_level: GolfLevel
  primary_goals: PrimaryGoal[]
  weekly_practice_frequency: WeeklyFreq
}

/**
 * PATCH /v1/users/me 的入参。
 * - 所有字段都可选，后端按 exclude_unset 只更新传入字段。
 * - `onboarding_completed` 仅允许置为 true（由引导"跳过"流程使用），置 false 会被后端拒绝。
 */
export interface UserUpdateRequest {
  nickname?: string
  avatar_url?: string
  golf_level?: GolfLevel
  primary_goals?: PrimaryGoal[]
  weekly_practice_frequency?: WeeklyFreq
  onboarding_completed?: boolean
}

/* ==================== 挥杆分析 ==================== */
export interface PhaseScore {
  score: number
  label: string
  is_weakest?: boolean
}

export interface AnalysisIssue {
  type: string
  name: string
  severity: 'high' | 'medium' | 'low'
  description: string
  key_frame_url?: string
  key_frame_timestamp?: number
}

export interface AnalysisRecommendation {
  drill_id: string
  name: string
  target_issue: string
  description: string
  duration_minutes: number
  sets: number
  steps: string[]
}

export interface SwingAnalysis {
  id: string
  user_id: string
  status: AnalysisStatus
  camera_angle: CameraAngle
  club_type: ClubType
  video_url: string
  skeleton_video_url?: string
  thumbnail_url?: string
  overall_score?: number
  score_change?: number
  score_level?: 'excellent' | 'good' | 'fair' | 'needs_improvement'
  phase_scores?: Record<string, PhaseScore>
  issues: AnalysisIssue[]
  recommendations: AnalysisRecommendation[]
  analyzed_at?: string
  created_at: string
}
