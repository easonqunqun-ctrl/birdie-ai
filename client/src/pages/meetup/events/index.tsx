/**
 * P2-M13-08 · 挑战赛列表
 */

import { FC, useCallback, useState } from 'react'
import { View, Text, ScrollView, Button } from '@tarojs/components'
import Taro, { useDidShow } from '@tarojs/taro'
import { PHASE2_MEETUP_ENABLED_FLAG } from '@/constants/flags'
import { meetupEventService, type MeetupEventRead } from '@/services/meetupEventService'
import './index.scss'

function formatWhen(iso: string | null): string {
  if (!iso) return '时间待定'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getMonth() + 1}/${d.getDate()} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

const MeetupEventsPage: FC = () => {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [items, setItems] = useState<MeetupEventRead[]>([])

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await meetupEventService.list({ page: 1, page_size: 50 })
      setItems(res.items)
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }, [])

  useDidShow(() => {
    if (!PHASE2_MEETUP_ENABLED_FLAG) {
      Taro.navigateBack()
      return
    }
    void load()
  })

  const goCreate = () => {
    Taro.navigateTo({ url: '/pages/meetup/events/create' })
  }

  const goDetail = (id: string) => {
    Taro.navigateTo({ url: `/pages/meetup/events/detail?id=${encodeURIComponent(id)}` })
  }

  return (
    <View className='meetup-events'>
      <View
        className='meetup-events__link'
        onClick={() => Taro.navigateBack()}
      >
        <Text>← 返回约球</Text>
      </View>

      {loading && (
        <View className='meetup-events__empty'>
          <Text>加载中…</Text>
        </View>
      )}

      {!loading && error && (
        <View className='meetup-events__empty'>
          <Text>{error}</Text>
        </View>
      )}

      {!loading && !error && items.length === 0 && (
        <View className='meetup-events__empty'>
          <Text>暂无进行中的挑战赛</Text>
          <Text>发起一场推杆 / 距离 / 综合分小挑战</Text>
        </View>
      )}

      {!loading && !error && items.length > 0 && (
        <ScrollView scrollY>
          {items.map((it) => (
            <View key={it.id} className='meetup-events__card' onClick={() => goDetail(it.id)}>
              <Text className='meetup-events__title'>{it.title}</Text>
              <Text className='meetup-events__meta'>
                {it.template_label || it.template_code} · {it.participant_count}/
                {it.capacity ?? 8} 人
              </Text>
              <Text className='meetup-events__meta'>{formatWhen(it.scheduled_at)}</Text>
            </View>
          ))}
        </ScrollView>
      )}

      <View className='meetup-events__fab-wrap'>
        <Button className='meetup-events__fab' onClick={goCreate}>
          发起挑战赛
        </Button>
      </View>
    </View>
  )
}

export default MeetupEventsPage
