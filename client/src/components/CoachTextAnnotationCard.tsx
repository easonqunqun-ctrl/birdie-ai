/**
 * M8-04 · 教练文字批注卡片（学员报告展示）。
 */

import { FC } from 'react'
import { View, Text } from '@tarojs/components'
import type { CoachAnnotationClipRef } from '@/services/coachAnnotationService'
import './CoachTextAnnotationCard.scss'

export interface CoachTextAnnotationCardProps {
  annotation: CoachAnnotationClipRef
}

const CoachTextAnnotationCard: FC<CoachTextAnnotationCardProps> = ({ annotation }) => {
  const text = (annotation.text_content || '').trim()
  if (!text) return null

  return (
    <View className='coach-text-ann'>
      <Text className='coach-text-ann__label'>教练点评</Text>
      <Text className='coach-text-ann__body'>{text}</Text>
    </View>
  )
}

export default CoachTextAnnotationCard
