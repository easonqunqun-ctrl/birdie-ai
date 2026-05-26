/**
 * P2-M7-06 · TrustBadge 单元测试。
 *
 * 覆盖 kickoff §3.3 档位 + FR-3 重拍 CTA 触发条件。
 */

import {
  HIGH_CONFIDENCE_THRESHOLD,
  LOW_CONFIDENCE_THRESHOLD,
  resolveTrustTier,
  shouldRecommendRetake,
} from '@/components/TrustBadge'

describe('TrustBadge utilities', () => {
  describe('resolveTrustTier', () => {
    test('null/undefined → high（V1 兜底 1.0）', () => {
      expect(resolveTrustTier(null)).toBe('high')
      expect(resolveTrustTier(undefined)).toBe('high')
    })

    test('≥0.75 → high', () => {
      expect(resolveTrustTier(1.0)).toBe('high')
      expect(resolveTrustTier(0.81)).toBe('high')
      expect(resolveTrustTier(HIGH_CONFIDENCE_THRESHOLD)).toBe('high')
    })

    test('0.5 ≤ x < 0.75 → medium', () => {
      expect(resolveTrustTier(0.5)).toBe('medium')
      expect(resolveTrustTier(0.6)).toBe('medium')
      expect(resolveTrustTier(0.74)).toBe('medium')
    })

    test('<0.5 → low', () => {
      expect(resolveTrustTier(0.49)).toBe('low')
      expect(resolveTrustTier(0.3)).toBe('low')
      expect(resolveTrustTier(0)).toBe('low')
    })
  })

  describe('shouldRecommendRetake', () => {
    test('低可信度 → true', () => {
      expect(shouldRecommendRetake(0.39)).toBe(true)
      expect(shouldRecommendRetake(0.27)).toBe(true)
    })

    test('中/高可信度 → false', () => {
      expect(shouldRecommendRetake(LOW_CONFIDENCE_THRESHOLD)).toBe(false)
      expect(shouldRecommendRetake(0.6)).toBe(false)
      expect(shouldRecommendRetake(0.81)).toBe(false)
    })

    test('null/undefined → false（V1 兜底 1.0）', () => {
      expect(shouldRecommendRetake(null)).toBe(false)
      expect(shouldRecommendRetake(undefined)).toBe(false)
    })

    test('kickoff §3.2.3 典型值表对齐', () => {
      // 行 1: 标准三脚架 0.81 → 不重拍
      expect(shouldRecommendRetake(0.81)).toBe(false)
      // 行 2: 暗光抖动 0.39 → 重拍
      expect(shouldRecommendRetake(0.39)).toBe(true)
      // 行 3: 偏角 20° 0.27 → 重拍
      expect(shouldRecommendRetake(0.27)).toBe(true)
    })
  })

  describe('阈值常量与 kickoff §3.3 对齐', () => {
    test('HIGH_CONFIDENCE_THRESHOLD == 0.75', () => {
      expect(HIGH_CONFIDENCE_THRESHOLD).toBe(0.75)
    })

    test('LOW_CONFIDENCE_THRESHOLD == 0.5', () => {
      expect(LOW_CONFIDENCE_THRESHOLD).toBe(0.5)
    })
  })
})
