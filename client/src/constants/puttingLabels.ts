/** M10-01 · 推杆 mode 阶段/特征展示标签（与 backend putting constants 对齐） */

export const PUTTING_PHASE_ORDER = ['setup', 'backstroke', 'impact', 'follow'] as const
export type PuttingPhaseKey = (typeof PUTTING_PHASE_ORDER)[number]

export const PUTTING_PHASE_LABEL: Record<PuttingPhaseKey, string> = {
  setup: '瞄准准备',
  backstroke: '回摆',
  impact: '击球',
  follow: '送杆',
}

export const PUTTING_FEATURE_ORDER = [
  'pendulum_stability',
  'head_stability',
  'face_alignment',
  'tempo_ratio',
] as const
export type PuttingFeatureKey = (typeof PUTTING_FEATURE_ORDER)[number]

export const PUTTING_FEATURE_LABEL: Record<PuttingFeatureKey, string> = {
  pendulum_stability: '钟摆稳定度',
  head_stability: '头部稳定',
  face_alignment: '推杆面方正',
  tempo_ratio: '节奏比',
}

export const PUTTING_PHASE_COLOR: Record<PuttingPhaseKey, string> = {
  setup: 'var(--color-info)',
  backstroke: 'var(--color-primary)',
  impact: 'var(--color-gold)',
  follow: 'var(--color-accent-mint)',
}
