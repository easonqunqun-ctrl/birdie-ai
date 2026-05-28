/**
 * P2-W11 · trustLabel.ts 工具单测
 *
 * 测试 `formatTrustMiniLabel` 是 W11 历史列表新加的；其它函数在 TrustBadge / 海报
 * 已有 e2e 覆盖，这里只补 tier 边界 + null 兜底，避免回归。
 */
import {
  formatTrustCompactLabel,
  formatTrustMiniLabel,
  HIGH_CONFIDENCE_THRESHOLD,
  LOW_CONFIDENCE_THRESHOLD,
  resolveTrustTier,
  shouldRecommendRetake,
} from '../trustLabel'

describe('resolveTrustTier', () => {
  it('returns high for >= 0.75', () => {
    expect(resolveTrustTier(0.9)).toBe('high')
    expect(resolveTrustTier(HIGH_CONFIDENCE_THRESHOLD)).toBe('high')
  })
  it('returns medium for [0.5, 0.75)', () => {
    expect(resolveTrustTier(0.5)).toBe('medium')
    expect(resolveTrustTier(0.74)).toBe('medium')
  })
  it('returns low for < 0.5', () => {
    expect(resolveTrustTier(0.0)).toBe('low')
    expect(resolveTrustTier(0.49)).toBe('low')
  })
  it('treats null/undefined as 1.0 (V1 legacy)', () => {
    expect(resolveTrustTier(null)).toBe('high')
    expect(resolveTrustTier(undefined)).toBe('high')
  })
})

describe('shouldRecommendRetake', () => {
  it('true only when below low threshold', () => {
    expect(shouldRecommendRetake(LOW_CONFIDENCE_THRESHOLD - 0.001)).toBe(true)
    expect(shouldRecommendRetake(LOW_CONFIDENCE_THRESHOLD)).toBe(false)
    expect(shouldRecommendRetake(0.9)).toBe(false)
    expect(shouldRecommendRetake(null)).toBe(false)
  })
})

describe('formatTrustCompactLabel', () => {
  it('contains tier text and percentage', () => {
    expect(formatTrustCompactLabel(0.83)).toBe('AI 高可信 83%')
    expect(formatTrustCompactLabel(0.6)).toBe('AI 中等可信 60%')
    expect(formatTrustCompactLabel(0.3)).toBe('AI 低可信 30%')
  })
  it('legacy null → 高可信 100%', () => {
    expect(formatTrustCompactLabel(null)).toBe('AI 高可信 100%')
  })
})

describe('formatTrustMiniLabel', () => {
  // 列表卡片场景：信息密度高，不带百分比
  it('drops percentage and keeps tier text', () => {
    expect(formatTrustMiniLabel(0.83)).toBe('AI 高可信')
    expect(formatTrustMiniLabel(0.6)).toBe('AI 中等可信')
    expect(formatTrustMiniLabel(0.3)).toBe('AI 低可信')
  })
  it('null tolerated', () => {
    expect(formatTrustMiniLabel(null)).toBe('AI 高可信')
    expect(formatTrustMiniLabel(undefined)).toBe('AI 高可信')
  })
})
