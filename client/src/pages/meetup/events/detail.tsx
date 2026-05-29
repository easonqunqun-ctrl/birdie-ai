/**
 * P2-M13-08 · 挑战赛详情（报名 / 提交成绩 / 排行）
 */

import { FC, useCallback, useState } from 'react'
import { View, Text, Input, Button } from '@tarojs/components'
import Taro, { useDidShow, useRouter } from '@tarojs/taro'
import { PHASE2_MEETUP_ENABLED_FLAG } from '@/constants/flags'
import { meetupEventService, type MeetupEventRead } from '@/services/meetupEventService'
import { useUserStore } from '@/store/userStore'
import './detail.scss'

const MeetupEventDetailPage: FC = () => {
  const router = useRouter()
  const eventId = (router.params.id || '').trim()
  const userId = useUserStore((s) => s.user?.id)

  const [loading, setLoading] = useState(true)
  const [event, setEvent] = useState<MeetupEventRead | null>(null)
  const [score, setScore] = useState('')
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    if (!eventId) return
    setLoading(true)
    try {
      const data = await meetupEventService.get(eventId)
      setEvent(data)
    } catch (e) {
      Taro.showToast({
        title: e instanceof Error ? e.message : '加载失败',
        icon: 'none',
      })
    } finally {
      setLoading(false)
    }
  }, [eventId])

  useDidShow(() => {
    if (!PHASE2_MEETUP_ENABLED_FLAG) {
      Taro.navigateBack()
      return
    }
    void load()
  })

  const onJoin = async () => {
    if (!eventId) return
    setBusy(true)
    try {
      const data = await meetupEventService.join(eventId)
      setEvent(data)
      Taro.showToast({ title: '报名成功', icon: 'success' })
    } catch (e) {
      Taro.showToast({
        title: e instanceof Error ? e.message : '报名失败',
        icon: 'none',
      })
    } finally {
      setBusy(false)
    }
  }

  const onSubmitScore = async () => {
    if (!eventId) return
    const value = Number(score)
    if (!Number.isFinite(value) || value < 0) {
      Taro.showToast({ title: '请输入有效成绩', icon: 'none' })
      return
    }
    setBusy(true)
    try {
      const data = await meetupEventService.submitScore(eventId, {
        self_reported_score: value,
      })
      setEvent(data)
      Taro.showToast({ title: '成绩已提交', icon: 'success' })
    } catch (e) {
      Taro.showToast({
        title: e instanceof Error ? e.message : '提交失败',
        icon: 'none',
      })
    } finally {
      setBusy(false)
    }
  }

  const joined = !!event?.my_participation_status
  const completed = !!event?.my_completion_badge

  if (loading || !event) {
    return (
      <View className='meetup-event-detail'>
        <Text>{loading ? '加载中…' : '活动不存在'}</Text>
      </View>
    )
  }

  return (
    <View className='meetup-event-detail'>
      <View className='meetup-event-detail__hero'>
        <Text className='meetup-event-detail__title'>{event.title}</Text>
        <Text className='meetup-event-detail__meta'>
          {event.template_label} · {event.participant_count}/{event.capacity ?? 8} 人
        </Text>
        {event.my_completion_badge && (
          <View className='meetup-event-detail__badge'>
            <Text>
              🏅 {String(event.my_completion_badge.title || '完赛荣誉徽章')}（无现金/实物奖励）
            </Text>
          </View>
        )}
      </View>

      <Text className='meetup-event-detail__section-title'>排行榜</Text>
      {event.leaderboard.length === 0 ? (
        <Text className='meetup-event-detail__meta'>暂无已审核成绩</Text>
      ) : (
        event.leaderboard.map((row) => (
          <View key={row.participation_id} className='meetup-event-detail__row'>
            <Text>
              #{row.rank} {row.user_id === userId ? '我' : `球友 ${row.user_id.slice(-4)}`}
            </Text>
            <Text>
              {row.self_reported_score} {event.score_label || ''}
            </Text>
          </View>
        ))
      )}

      <View className='meetup-event-detail__actions'>
        {!joined && (
          <Button className='meetup-event-detail__btn' loading={busy} onClick={() => void onJoin()}>
            报名参加
          </Button>
        )}
        {joined && !completed && (
          <>
            <Input
              className='meetup-event-detail__score-input'
              type='digit'
              value={score}
              placeholder={`输入${event.score_label || '成绩'}`}
              onInput={(e) => setScore(e.detail.value)}
            />
            <Button
              className='meetup-event-detail__btn'
              loading={busy}
              onClick={() => void onSubmitScore()}
            >
              提交自报成绩
            </Button>
          </>
        )}
        <Button
          className='meetup-event-detail__btn-secondary'
          onClick={() => Taro.navigateBack()}
        >
          返回列表
        </Button>
      </View>
    </View>
  )
}

export default MeetupEventDetailPage
