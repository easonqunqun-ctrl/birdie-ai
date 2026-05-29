/**
 * P2-M12-03 · 球手对比库列表页：每周精选 banner + 可选球手 → 进详情看 clips。
 */

import { FC, useCallback, useState } from 'react'
import { View, Text, ScrollView, Image } from '@tarojs/components'
import Taro, { useDidShow } from '@tarojs/taro'
import { PHASE2_PROS_ENABLED_FLAG } from '@/constants/flags'
import {
  prosService,
  type ProPlayerRead,
  type ProTopicRead,
} from '@/services/prosService'
import './index.scss'

const ProsIndexPage: FC = () => {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [players, setPlayers] = useState<ProPlayerRead[]>([])
  const [weeklyTopic, setWeeklyTopic] = useState<ProTopicRead | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [playerList, topic] = await Promise.all([
        prosService.list(),
        prosService.currentTopic().catch(() => null),
      ])
      setPlayers(playerList)
      setWeeklyTopic(topic)
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

  const openWeeklyTopic = () => {
    Taro.navigateTo({ url: '/pages/pros/topic' }).catch(() => undefined)
  }

  if (!PHASE2_PROS_ENABLED_FLAG) {
    return (
      <View className='pros-list pros-list--blocked'>
        <Text>功能维护中…</Text>
      </View>
    )
  }

  if (loading) {
    return (
      <View className='pros-list pros-list--empty'>
        <Text>加载中…</Text>
      </View>
    )
  }

  if (error) {
    return (
      <View className='pros-list pros-list--empty'>
        <Text className='pros-list__error'>{error}</Text>
        <View className='pros-list__retry' onClick={() => void load()}>
          <Text>重试</Text>
        </View>
      </View>
    )
  }

  const onTap = (player: ProPlayerRead) => {
    Taro.navigateTo({
      url: `/pages/pros/detail?id=${encodeURIComponent(player.id)}`,
    })
  }

  return (
    <ScrollView scrollY className='pros-list'>
      {weeklyTopic && (
        <View
          className='pros-list__banner'
          onClick={openWeeklyTopic}
          style={
            weeklyTopic.banner_url
              ? { backgroundImage: `url(${weeklyTopic.banner_url})` }
              : undefined
          }
        >
          <Text className='pros-list__banner-tag'>每周精选</Text>
          <Text className='pros-list__banner-title'>{weeklyTopic.title}</Text>
          {weeklyTopic.subtitle && (
            <Text className='pros-list__banner-subtitle'>{weeklyTopic.subtitle}</Text>
          )}
          <Text className='pros-list__banner-cta'>查看专题 ›</Text>
        </View>
      )}

      {players.length === 0 ? (
        <View className='pros-list__empty-inline'>
          <Text>暂无球手，敬请期待</Text>
        </View>
      ) : (
        players.map((player) => (
          <View
            key={player.id}
            className='pros-list__card'
            onClick={() => onTap(player)}
          >
            {player.avatar_url ? (
              <Image
                className='pros-list__avatar'
                src={player.avatar_url}
                mode='aspectFill'
              />
            ) : (
              <View className='pros-list__avatar pros-list__avatar--placeholder'>
                <Text>{player.name.slice(0, 1)}</Text>
              </View>
            )}
            <View className='pros-list__main'>
              <Text className='pros-list__name'>{player.name}</Text>
              {player.name_en && (
                <Text className='pros-list__name-en'>{player.name_en}</Text>
              )}
              <View className='pros-list__meta'>
                {player.nationality && (
                  <Text className='pros-list__meta-item'>{player.nationality}</Text>
                )}
                <Text className='pros-list__meta-item'>
                  {player.handedness === 'right' ? '右手' : '左手'}
                </Text>
                {player.height_cm && (
                  <Text className='pros-list__meta-item'>
                    {player.height_cm}cm
                  </Text>
                )}
              </View>
            </View>
            <Text className='pros-list__arrow'>›</Text>
          </View>
        ))
      )}
    </ScrollView>
  )
}

export default ProsIndexPage
