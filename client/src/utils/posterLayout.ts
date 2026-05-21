/**
 * 分享海报版式（Q-C1）
 *
 * 设计稿 750×1334（@2x，等同 375×667pt），与小程序竖屏比例一致。
 *
 * - 纯函数；不依赖 Canvas/DOM，方便 jest 覆盖布局。
 * - 颜色严格走品牌四色（白皮书 §7.2）：靛蓝 / 白 / 金 / 点缀绿；
 *   *Canvas 不支持 CSS 变量*，这里 HEX 与 `client/src/app.scss` Token 一一对齐。
 * - 6D 雷达图坐标转换沿用 `RadarChart.tsx` 的极坐标公式。
 */

import type { AnalysisScoreLevel } from '@/types/analysis'

/** 海报画布尺寸（CSS px，Canvas 2D 内部按 dpr 缩放） */
export const POSTER_WIDTH = 750
export const POSTER_HEIGHT = 1334

/** 与 app.scss 中 brand token 完全对齐；Canvas 用 HEX */
export const POSTER_COLORS = {
  primary: '#1a237e',
  primaryDark: '#0d1657',
  primarySoft: '#3949ab',
  gold: '#c9a227',
  white: '#ffffff',
  ink: '#1f2937',
  inkSoft: '#4b5563',
  inkMuted: '#9ca3af',
  border: '#e5e7eb',
  accentMint: '#00d084',
  warning: '#f59e0b',
  error: '#ef4444',
  info: '#3b82f6',
} as const

/** score_level → 主色（与 SCORE_LEVEL_META 对齐，但 HEX 化） */
export function levelColor(level: AnalysisScoreLevel | null | undefined): string {
  switch (level) {
    case 'excellent':
      return POSTER_COLORS.gold
    case 'great':
      return POSTER_COLORS.primary
    case 'good':
      return POSTER_COLORS.info
    case 'fair':
      return POSTER_COLORS.warning
    case 'needs_improvement':
      return POSTER_COLORS.error
    default:
      return POSTER_COLORS.primary
  }
}

/** 由分数兜底推 level（与 scoreLevelFromScore 对齐，避免 hooks 互相引用） */
export function deriveLevel(score: number | null | undefined): AnalysisScoreLevel | null {
  if (score === null || score === undefined) return null
  if (score >= 90) return 'excellent'
  if (score >= 80) return 'great'
  if (score >= 70) return 'good'
  if (score >= 60) return 'fair'
  return 'needs_improvement'
}

/** 极坐标 → 笛卡尔坐标（顶部 0°，顺时针） */
export interface PolarPoint {
  x: number
  y: number
}

export function radarPoint(
  centerX: number,
  centerY: number,
  radius: number,
  axisIndex: number,
  axisCount: number,
  valueRatio: number,
): PolarPoint {
  const safeRatio = Math.max(0, Math.min(1, valueRatio))
  const angle = (Math.PI * 2 * axisIndex) / axisCount - Math.PI / 2
  return {
    x: centerX + radius * safeRatio * Math.cos(angle),
    y: centerY + radius * safeRatio * Math.sin(angle),
  }
}

/** 单一阶段在海报雷达图上的标签锚点（用于决定 textAlign / textBaseline） */
export interface AxisLabelAnchor {
  x: number
  y: number
  align: 'left' | 'center' | 'right'
  baseline: 'top' | 'middle' | 'bottom'
}

export function axisLabelAnchor(
  centerX: number,
  centerY: number,
  radius: number,
  axisIndex: number,
  axisCount: number,
): AxisLabelAnchor {
  const p = radarPoint(centerX, centerY, radius, axisIndex, axisCount, 1)
  const eps = 0.5
  let align: AxisLabelAnchor['align'] = 'center'
  if (p.x > centerX + eps) align = 'left'
  else if (p.x < centerX - eps) align = 'right'

  let baseline: AxisLabelAnchor['baseline'] = 'middle'
  if (p.y > centerY + eps) baseline = 'top'
  else if (p.y < centerY - eps) baseline = 'bottom'

  return { x: p.x, y: p.y, align, baseline }
}

/** 输入：报告必要字段（按 PublicReport 子集，避免对登录态依赖） */
export interface PosterInput {
  /** 综合分（0-100）；可为空（脱敏后没分）→ 走「保存」兜底 */
  overallScore: number | null
  scoreLevel: AnalysisScoreLevel | null
  /** 6D 阶段分；顺序与 PHASE_ORDER 一致 */
  phaseScores: number[]
  /** 6D 标签（站位 / 上杆 / ...） */
  phaseLabels: string[]
  /** 球杆中文标签（"7 号铁" 等） */
  clubLabel: string
  /** 截图缩略图（可选）；通常已是 https url */
  thumbnailUrl: string | null
  /** 小程序码 PNG 本地路径或网络 url */
  wxaCodeUrl: string | null
  /** 主要问题最多取 3 条（脱敏 / 完整都有） */
  topIssues: string[]
  /** 拍摄角度（"正面" / "侧面" 等） */
  cameraAngleLabel: string
}

/** 截断中文/英文 label，避免标签溢出 Canvas */
export function truncateLabel(text: string, maxChars: number): string {
  if (!text) return ''
  if (maxChars <= 0) return ''
  if (text.length <= maxChars) return text
  if (maxChars <= 1) return text.slice(0, 1)
  return `${text.slice(0, maxChars - 1)}…`
}
