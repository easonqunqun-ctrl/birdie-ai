/**
 * VideoCard — AI 回复里的练习示范视频卡片（v1.1.1）
 */

import { FC, useCallback, useState } from 'react'
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
  const [localSrc, setLocalSrc] = useState('')
  const [loading, setLoading] = useState(false)
  const [buffering, setBuffering] = useState(false)

  const handleVideoError = useCallback(() => {
    setPlaying(false)
    setBuffering(false)
    setLoading(false)
    Taro.hideLoading()
    Taro.showToast({ title: '示范视频加载失败', icon: 'none', duration: 2000 })
  }, [])

  const startPlay = useCallback(async () => {
    if (!detail || loading) return

    if (localSrc) {
      setPlaying(true)
      return
    }

    setLoading(true)
    Taro.showLoading({ title: '加载视频', mask: true })
    try {
      const res = await Taro.downloadFile({ url: detail.video_url })
      if (res.statusCode !== 200 || !res.tempFilePath) {
        throw new Error('download failed')
      }
      setLocalSrc(res.tempFilePath)
      setPlaying(true)
    } catch {
      Taro.showToast({ title: '示范视频加载失败', icon: 'none', duration: 2000 })
    } finally {
      setLoading(false)
      Taro.hideLoading()
    }
  }, [detail, loading, localSrc])

  if (!detail) return null

  const poster = posterBroken ? undefined : (detail.poster_url || attachment.poster_url)
  const videoSrc = localSrc || detail.video_url

  return (
    <View className='video-card'>
      <View className='video-card__head'>
        <Text className='video-card__badge'>示范视频</Text>
        <Text className='video-card__title'>{detail.title}</Text>
      </View>
      {playing ? (
        <View className='video-card__player-wrap'>
          <Video
            className='video-card__player'
            src={videoSrc}
            poster={poster}
            controls
            showCenterPlayBtn
            showLoading
            objectFit='contain'
            onEnded={() => {
              setPlaying(false)
              setBuffering(false)
            }}
            onPlay={() => setBuffering(false)}
            onWaiting={() => setBuffering(true)}
            onError={handleVideoError}
          />
          {buffering ? (
            <View className='video-card__buffering'>
              <Text className='video-card__buffering-text'>缓冲中…</Text>
            </View>
          ) : null}
        </View>
      ) : (
        <View className='video-card__preview' onClick={startPlay}>
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
            <Text className='video-card__play-icon'>{loading ? '…' : '▶'}</Text>
            <Text className='video-card__play-label'>
              {loading ? '加载中' : '点击播放'}
            </Text>
          </View>
        </View>
      )}
      <Text className='video-card__hint-note'>开源高尔夫素材示范，专属教学片陆续更新</Text>
    </View>
  )
}

export default VideoCard
