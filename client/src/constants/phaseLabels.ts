/**
 * 挥杆 6 阶段标签映射
 *
 * 阶段 key 与 `ai_engine/app/mock_pipeline.py::PHASE_LABELS` / backend
 * `phase_scores` / `phase_timestamps` 字典的 key 严格一致。
 *
 * 6 色分段用于报告页的"阶段色条"：保证相邻阶段颜色不撞，且首尾色对应用户直觉
 * （setup 浅灰 → follow_through 金色收）。
 */

export type SwingPhaseKey =
  | 'setup'
  | 'backswing'
  | 'top'
  | 'downswing'
  | 'impact'
  | 'follow_through'

export const PHASE_ORDER: SwingPhaseKey[] = [
  'setup',
  'backswing',
  'top',
  'downswing',
  'impact',
  'follow_through',
]

export const PHASE_LABEL: Record<SwingPhaseKey, string> = {
  setup: '站位',
  backswing: '上杆',
  top: '顶点',
  downswing: '下杆',
  impact: '击球',
  follow_through: '收杆',
}

export const PHASE_FULL_LABEL: Record<SwingPhaseKey, string> = {
  setup: '站位准备',
  backswing: '上杆轨迹',
  top: '顶点位置',
  downswing: '下杆转换',
  impact: '击球触球',
  follow_through: '收杆平衡',
}

/** 阶段色条颜色（从左到右） */
export const PHASE_COLOR: Record<SwingPhaseKey, string> = {
  setup: '#94a3b8',
  backswing: '#60a5fa',
  top: '#a78bfa',
  downswing: '#f472b6',
  impact: '#f97316',
  follow_through: '#c9a227',
}
