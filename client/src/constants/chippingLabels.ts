/** M10-02 · 切杆 mode 阶段/特征展示标签 */

export const CHIPPING_PHASE_ORDER = ['setup', 'backswing', 'impact', 'follow'] as const
export type ChippingPhaseKey = (typeof CHIPPING_PHASE_ORDER)[number]

export const CHIPPING_PHASE_LABEL: Record<ChippingPhaseKey, string> = {
  setup: '瞄准准备',
  backswing: '上杆',
  impact: '击球',
  follow: '收杆',
}

export const CHIPPING_FEATURE_ORDER = [
  'half_swing_amplitude',
  'face_open_angle',
  'contact_point_quality',
] as const
export type ChippingFeatureKey = (typeof CHIPPING_FEATURE_ORDER)[number]

export const CHIPPING_FEATURE_LABEL: Record<ChippingFeatureKey, string> = {
  half_swing_amplitude: '半挥幅度',
  face_open_angle: '杆面开角',
  contact_point_quality: '触球质量',
}

export const CHIPPING_CLUB_HINT = ['wedge', 'iron_8', 'iron_9'] as const
