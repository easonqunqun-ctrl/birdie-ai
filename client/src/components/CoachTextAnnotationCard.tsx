/**
 * M8-04 · 教练文字批注卡片（学员报告展示）。
 */

import { FC } from 'react'
import { View, Text } from '@tarojs/components'
import type { CoachAnnotationClipRef } from '@/services/coachAnnotationService'
import './CoachTextAnnotationCard.scss'

export interface CoachTextAnnotationCardProps {
  annotation: CoachAnnotationClipRef
  /** 教练端编辑模式：展示删除 */
  onDelete?: (annotationId: string) => void
}

const CoachTextAnnotationCard: FC<CoachTextAnnotationCardProps> = ({
  annotation,
  onDelete,
}) => {
  const text = (annotation.text_content || '').trim()
  if (!text) return null

  return (
    <View className='coach-text-ann'>
      <View className='coach-text-ann__head'>
        <Text className='coach-text-ann__label'>教练点评</Text>
        {onDelete ? (
          <Text
            className='coach-text-ann__delete'
            onClick={() => onDelete(annotation.id)}
          >
            删除
          </Text>
        ) : null}
      </View>
      <Text className='coach-text-ann__body'>{text}</Text>
    </View>
  )
}

export default CoachTextAnnotationCard
