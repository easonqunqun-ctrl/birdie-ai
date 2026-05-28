/**
 * P2-M7-06 · 分析可信度 tier 与文案（TrustBadge / 海报共用）
 */

export type TrustTier = 'high' | 'medium' | 'low'

export const HIGH_CONFIDENCE_THRESHOLD = 0.75
export const LOW_CONFIDENCE_THRESHOLD = 0.5

export function resolveTrustTier(confidence: number | null | undefined): TrustTier {
  const value = confidence ?? 1.0
  if (value >= HIGH_CONFIDENCE_THRESHOLD) return 'high'
  if (value >= LOW_CONFIDENCE_THRESHOLD) return 'medium'
  return 'low'
}

export function shouldRecommendRetake(confidence: number | null | undefined): boolean {
  const value = confidence ?? 1.0
  return value < LOW_CONFIDENCE_THRESHOLD
}

const TIER_COMPACT_TITLE: Record<TrustTier, string> = {
  high: 'AI 高可信',
  medium: 'AI 中等可信',
  low: 'AI 低可信',
}

/** 海报等窄区域用的单行标签（含百分比） */
export function formatTrustCompactLabel(confidence: number | null | undefined): string {
  const tier = resolveTrustTier(confidence)
  const pct = Math.round((confidence ?? 1.0) * 100)
  return `${TIER_COMPACT_TITLE[tier]} ${pct}%`
}

/**
 * P2-W11 · 历史列表卡片用的极短可信度标签（不含百分比）
 *
 * 卡片信息密度高，留给 trust 标签的横向空间只有几个字；带百分比反而干扰
 * "分数 vs 可信度"的视觉层级。所以列表里只显示「高/中/低」三档。
 */
const TIER_MINI_LABEL: Record<TrustTier, string> = {
  high: 'AI 高可信',
  medium: 'AI 中等可信',
  low: 'AI 低可信',
}
export function formatTrustMiniLabel(confidence: number | null | undefined): string {
  return TIER_MINI_LABEL[resolveTrustTier(confidence)]
}
