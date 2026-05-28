/**
 * P2-M7-06：报告页可信度色块 + 可选"建议重拍" CTA
 *
 * 来源：docs/release-notes/p2-m7-06-confidence-pipeline-kickoff.md §3.3
 *
 * - ≥ 0.75 高（绿/mint）："AI 高可信"
 * - 0.5–0.75 中（金/gold）："AI 中等可信，可参考"
 * - < 0.5  低（灰 + 警告条）："AI 难以做出可靠分析"，伴随重拍 CTA
 *
 * V1 报告兜底 1.0；客户端收到 null 也按 1.0 走（不展示色块）。
 *
 * 颜色严格走 `client/src/app.scss` CSS 变量，**禁硬编码 HEX**（AGENTS.md §3）。
 */

import { FC } from 'react'
import { View, Text } from '@tarojs/components'
import {
  resolveTrustTier,
  shouldRecommendRetake,
  type TrustTier,
} from '@/utils/trustLabel'
import './TrustBadge.scss'

export type { TrustTier } from '@/utils/trustLabel'
export {
  HIGH_CONFIDENCE_THRESHOLD,
  LOW_CONFIDENCE_THRESHOLD,
  resolveTrustTier,
  shouldRecommendRetake,
} from '@/utils/trustLabel'

const TIER_COPY: Record<TrustTier, { title: string; hint: string }> = {
  high: {
    title: 'AI 高可信',
    hint: '画质、机位、姿态识别均良好，本次分析结果可信。',
  },
  medium: {
    title: 'AI 中等可信，可参考',
    hint: '部分信号偏弱，建议在更好的光线/机位下再拍一段对比。',
  },
  low: {
    title: 'AI 难以做出可靠分析',
    hint: '画质或机位影响识别，建议按提示重拍后再分析。',
  },
}

export interface TrustBadgeProps {
  /** P2-M7-06 analysis_confidence，0-1；null/undefined 按 1.0 兜底 */
  confidence: number | null | undefined
  /** 低可信度时点击"重拍"回调 */
  onRetake?: () => void
}

const TrustBadge: FC<TrustBadgeProps> = ({ confidence, onRetake }) => {
  const tier = resolveTrustTier(confidence)
  const copy = TIER_COPY[tier]
  const showRetake = tier === 'low' && !!onRetake
  const percentLabel = `${Math.round(((confidence ?? 1.0) * 100))}%`

  return (
    <View className={`trust-badge trust-badge--${tier}`}>
      <View className='trust-badge__row'>
        <Text className='trust-badge__title'>{copy.title}</Text>
        <Text className='trust-badge__percent' aria-label='AI 整体置信度'>
          {percentLabel}
        </Text>
      </View>
      <Text className='trust-badge__hint'>{copy.hint}</Text>
      {showRetake && (
        <View
          className='trust-badge__cta'
          onClick={onRetake}
          hoverClass='trust-badge__cta--hover'
        >
          <Text className='trust-badge__cta-text'>立即重拍一段</Text>
        </View>
      )}
    </View>
  )
}

export default TrustBadge
