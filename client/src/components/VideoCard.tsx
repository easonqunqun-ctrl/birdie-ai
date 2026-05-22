/**
 * VideoCard — AI 回复里的练习示范视频卡片（v1.1.1）
 */

import { FC, useState } from 'react'
import { View, Text, Video, Image } from '@tarojs/components'
import Taro from '@tarojs/taro'
import type { VideoCardAttachment } from '@/types/chat'
import { resolveVideoCardDetail } from '@/constants/drillVideoLibrary'
import './VideoCard.scss'

export interface VideoCardProps {
  attachment: VideoCardAttachment
}

export const VideoCard: FC<VideoCardProps> = ({ attachment }) => {
  const detail = resolveVideoCardDetail(attachment)
  const [playing, setPlaying] = useState(false)
  const [posterBroken, setPosterBroken] = useState(false)

  if (!detail) return null

  const poster = posterBroken ? undefined : (detail.poster_url || attachment.poster_url)

  const handleVideoError = () => {
    setPlaying(false)
    Taro.showToast({ title: '示范视频加载失败', icon: 'none', duration: 2000 })
  }

  return (
    <View className='video-card'>
      <View className='video-card__head'>
        <Text className='video-card__badge'>示范视频</Text>
        <Text className='video-card__title'>{detail.title}</Text>
      </View>
      {playing ? (
        <Video
          className='video-card__player'
          src={detail.video_url}
          poster={poster}
          controls
          showCenterPlayBtn
          objectFit='contain'
          onEnded={() => setPlaying(false)}
          onError={handleVideoError}
        />
      ) : (
        <View className='video-card__preview' onClick={() => setPlaying(true)}>
          {poster ? (
            <Image
              className='video-card__poster'
              src={poster}
              mode='aspectFill'
              onError={() => setPosterBroken(true)}
            />
          ) : (
            <View className='video-card__poster video-card__poster--placeholder' />
          )}
          <View className='video-card__play-mask'>
            <Text className='video-card__play-icon'>▶</Text>
            <Text className='video-card__play-label'>点击播放</Text>
          </View>
        </View>
      )}
      <Text className='video-card__hint-note'>开源高尔夫素材示范，专属教学片陆续更新</Text>
    </View>
  )
}

export default VideoCard
