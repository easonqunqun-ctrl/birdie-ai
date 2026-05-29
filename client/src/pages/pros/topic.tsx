/**
 * P2-M12-06 · 每周精选详情：banner + 专题镜头列表。
 */

import { FC, useCallback, useState } from 'react'
import { View, Text, ScrollView, Image } from '@tarojs/components'
import Taro, { useDidShow } from '@tarojs/taro'
import { PHASE2_PROS_ENABLED_FLAG } from '@/constants/flags'
import { prosService, type ProTopicRead } from '@/services/prosService'
import './topic.scss'

const ProsTopicPage: FC = () => {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [topic, setTopic] = useState<ProTopicRead | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await prosService.currentTopic()
      setTopic(data)
      if (!data) setError('本周暂无精选专题')
    } catch (e) {
      const msg = e instanceof Error ? e.message : '加载失败'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }, [])

  useDidShow(() => {
    if (!PHASE2_PROS_ENABLED_FLAG) {
      Taro.showToast({ title: '该功能尚未开放', icon: 'none' })
      setTimeout(() => Taro.navigateBack({ delta: 1 }), 1200)
      return
    }
    void load()
  })

  if (!PHASE2_PROS_ENABLED_FLAG) {
    return (
      <View className='pro-topic pro-topic--blocked'>
        <Text>功能维护中…</Text>
      </View>
    )
  }

  if (loading) {
    return (
      <View className='pro-topic pro-topic--empty'>
        <Text>加载中…</Text>
      </View>
    )
  }

  if (error || !topic) {
    return (
      <View className='pro-topic pro-topic--empty'>
        <Text className='pro-topic__error'>{error || '暂无专题'}</Text>
        <View className='pro-topic__back' onClick={() => Taro.navigateBack({ delta: 1 })}>
          <Text>返回</Text>
        </View>
      </View>
    )
  }

  return (
    <ScrollView scrollY className='pro-topic'>
      <View
        className='pro-topic__hero'
        style={
          topic.banner_url
            ? { backgroundImage: `url(${topic.banner_url})` }
            : undefined
        }
      >
        <Text className='pro-topic__hero-tag'>每周精选</Text>
        <Text className='pro-topic__hero-title'>{topic.title}</Text>
        {topic.subtitle && (
          <Text className='pro-topic__hero-subtitle'>{topic.subtitle}</Text>
        )}
      </View>

      {topic.summary && (
        <View className='pro-topic__summary'>
          <Text>{topic.summary}</Text>
        </View>
      )}

      <View className='pro-topic__clips'>
        <Text className='pro-topic__clips-title'>专题镜头 · {topic.clips.length}</Text>
        {topic.clips.map(({ clip, player }) => (
          <View
            key={clip.id}
            className='pro-topic__clip-card'
            onClick={() =>
              Taro.navigateTo({
                url: `/pages/pros/detail?id=${encodeURIComponent(player.id)}`,
              })
            }
          >
            {clip.thumbnail_url ? (
              <Image
                className='pro-topic__clip-thumb'
                src={clip.thumbnail_url}
                mode='aspectFill'
              />
            ) : (
              <View className='pro-topic__clip-thumb pro-topic__clip-thumb--placeholder'>
                <Text>{player.name.slice(0, 1)}</Text>
              </View>
            )}
            <View className='pro-topic__clip-main'>
              <Text className='pro-topic__clip-player'>{player.name}</Text>
              <Text className='pro-topic__clip-meta'>
                {clip.club_type} · {clip.camera_angle === 'face_on' ? '正面' : '侧线'}
              </Text>
              {clip.overall_score != null && (
                <Text className='pro-topic__clip-score'>{clip.overall_score} 分</Text>
              )}
              <Text className='pro-topic__clip-credit'>来源：{clip.source_credit}</Text>
            </View>
            <Text className='pro-topic__clip-arrow'>›</Text>
          </View>
        ))}
      </View>
    </ScrollView>
  )
}

export default ProsTopicPage
