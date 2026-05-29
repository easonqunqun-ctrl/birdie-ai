/**
 * M12-09 · 教练引用的职业镜头卡片（学员报告展示）。
 */

import { FC } from 'react'
import { View, Text, Image, Button } from '@tarojs/components'
import Taro from '@tarojs/taro'
import type { CoachAnnotationClipRef } from '@/services/coachAnnotationService'
import './ProClipReferenceCard.scss'

export interface ProClipReferenceCardProps {
  annotation: CoachAnnotationClipRef
  analysisId: string
}

const ProClipReferenceCard: FC<ProClipReferenceCardProps> = ({
  annotation,
  analysisId,
}) => {
  const { clip, player, clip_unavailable: unavailable, text_content: note } = annotation

  if (unavailable || !clip || !player) {
    return (
      <View className='pro-clip-ref pro-clip-ref--empty'>
        <Text className='pro-clip-ref__empty-text'>参考的职业镜头已下架</Text>
      </View>
    )
  }

  return (
    <View className='pro-clip-ref'>
      <Text className='pro-clip-ref__label'>教练推荐参考</Text>
      {note ? <Text className='pro-clip-ref__note'>{note}</Text> : null}
      <View className='pro-clip-ref__main'>
        {clip.thumbnail_url ? (
          <Image
            className='pro-clip-ref__thumb'
            src={clip.thumbnail_url}
            mode='aspectFill'
          />
        ) : (
          <View className='pro-clip-ref__thumb pro-clip-ref__thumb--placeholder' />
        )}
        <View className='pro-clip-ref__meta'>
          <Text className='pro-clip-ref__name'>{player.name}</Text>
          <Text className='pro-clip-ref__sub'>
            {clip.club_type} · {clip.overall_score != null ? `${clip.overall_score} 分` : '—'}
          </Text>
        </View>
      </View>
      <View className='pro-clip-ref__actions'>
        <Button
          className='pro-clip-ref__btn'
          onClick={() =>
            Taro.navigateTo({
              url: `/pages/pros/detail?id=${encodeURIComponent(player.id)}`,
            })
          }
        >
          资源库
        </Button>
        <Button
          className='pro-clip-ref__btn pro-clip-ref__btn--primary'
          onClick={() =>
            Taro.navigateTo({
              url: `/pages/analysis/pro-compare?id=${encodeURIComponent(analysisId)}&clipId=${encodeURIComponent(clip.id)}`,
            })
          }
        >
          看对比
        </Button>
      </View>
    </View>
  )
}

export default ProClipReferenceCard
