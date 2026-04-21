/**
 * 训练计划 / 打卡类型（对齐 backend/app/schemas/training.py）.
 *
 * 前端内置 `constants/drillLibrary.ts` 提供 drill 详情展示；
 * 后端 `/v1/drills` 仅在 W8 drill 库升级时作为远程数据源使用。
 */

export type TaskStatus = 'pending' | 'completed'
export type Difficulty = 'easy' | 'medium' | 'hard'

export interface TrainingTaskItem {
  id: string
  plan_id: string
  drill_id: string
  scheduled_date: string // YYYY-MM-DD
  sort_order: number
  status: TaskStatus
  completed_at: string | null
  verification_analysis_id: string | null
}

export interface TrainingPlanDetail {
  id: string
  user_id: string
  week_start: string
  week_end: string
  source_analysis_id: string | null
  ai_summary: string | null
  total_tasks: number
  completed_tasks: number
  tasks: TrainingTaskItem[]
  created_at: string
}

export interface CompleteTaskRequest {
  duration_minutes?: number
  notes?: string
}

export interface CompleteTaskResponse {
  task: TrainingTaskItem
  current_streak_days: number
  plan_completed_tasks: number
  plan_total_tasks: number
}

export interface PracticeLogItem {
  id: string
  drill_id: string
  task_id: string | null
  practice_date: string
  duration_minutes: number | null
  notes: string | null
  created_at: string
}
