/**
 * AnalysisCard — AI 回复里的历史分析报告卡片（v1.1.0）
 */

import { FC } from 'react'
import { View, Text } from '@tarojs/components'
import Taro from '@tarojs/taro'
import type { AnalysisCardAttachment } from '@/types/chat'
import './AnalysisCard.scss'

export interface AnalysisCardProps {
  attachment: AnalysisCardAttachment
}

export const AnalysisCard: FC<AnalysisCardProps> = ({ attachment }) => {
  const score =
    typeof attachment.overall_score === 'number'
      ? Math.round(attachment.overall_score)
      : null

  const openReport = () => {
    if (!attachment.analysis_id) return
    Taro.navigateTo({
      url: `/pages/analysis/report?id=${encodeURIComponent(attachment.analysis_id)}`,
    }).catch(() => undefined)
  }

  return (
    <View className='analysis-card' onClick={openReport}>
      <View className='analysis-card__head'>
        <Text className='analysis-card__badge'>挥杆报告</Text>
        {score !== null ? (
          <Text className='analysis-card__score'>{score} 分</Text>
        ) : (
          <Text className='analysis-card__score analysis-card__score--muted'>查看详情</Text>
        )}
      </View>
      <Text className='analysis-card__hint'>点击查看完整六维分析与训练建议</Text>
      <Text className='analysis-card__cta'>打开报告 ›</Text>
    </View>
  )
}

export default AnalysisCard
