/**
 * M8-03 · 学员处理教练邀请。
 */

import { FC, useCallback, useEffect, useState } from 'react'
import { View, Text, Button } from '@tarojs/components'
import Taro, { useDidShow } from '@tarojs/taro'
import { PHASE2_COACH_ENABLED_FLAG } from '@/constants/flags'
import {
  coachStudentsService,
  type CoachStudentRelationRead,
} from '@/services/coachStudentsService'
import './index.scss'

const CoachInvitePage: FC = () => {
  const [loading, setLoading] = useState(true)
  const [pending, setPending] = useState<CoachStudentRelationRead[]>([])
  const [active, setActive] = useState<CoachStudentRelationRead | null>(null)
  const [actingId, setActingId] = useState<string | null>(null)

  const load = useCallback(async () => {
    if (!PHASE2_COACH_ENABLED_FLAG) {
      setLoading(false)
      return
    }
    setLoading(true)
    try {
      const data = await coachStudentsService.myCoachOverview()
      setPending(data.pending)
      setActive(data.active)
    } catch (e) {
      Taro.showToast({
        title: e instanceof Error ? e.message : '加载失败',
        icon: 'none',
      })
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  useDidShow(() => {
    void load()
  })

  const accept = async (relationId: string) => {
    setActingId(relationId)
    try {
      await coachStudentsService.accept(relationId)
      Taro.showToast({ title: '已接受', icon: 'success' })
      await load()
    } catch (e) {
      Taro.showToast({
        title: e instanceof Error ? e.message : '操作失败',
        icon: 'none',
      })
    } finally {
      setActingId(null)
    }
  }

  const reject = async (relationId: string) => {
    setActingId(relationId)
    try {
      await coachStudentsService.reject(relationId)
      Taro.showToast({ title: '已拒绝', icon: 'none' })
      await load()
    } catch (e) {
      Taro.showToast({
        title: e instanceof Error ? e.message : '操作失败',
        icon: 'none',
      })
    } finally {
      setActingId(null)
    }
  }

  if (!PHASE2_COACH_ENABLED_FLAG) {
    return (
      <View className='coach-invite coach-invite--blocked'>
        <Text>教练功能尚未开放</Text>
      </View>
    )
  }

  if (loading) {
    return (
      <View className='coach-invite coach-invite--blocked'>
        <Text>加载中…</Text>
      </View>
    )
  }

  return (
    <View className='coach-invite'>
      {active && (
        <View className='coach-invite__section'>
          <Text className='coach-invite__section-title'>当前教练</Text>
          <Text className='coach-invite__name'>
            {active.coach?.display_name || active.coach?.nickname || '教练'}
          </Text>
          <Button
            className='coach-invite__ghost'
            onClick={() =>
              Taro.navigateTo({ url: '/pages/profile/coach-visibility' })
            }
          >
            管理可见字段
          </Button>
        </View>
      )}

      <View className='coach-invite__section'>
        <Text className='coach-invite__section-title'>待处理邀请</Text>
        {pending.length === 0 ? (
          <Text className='coach-invite__empty'>暂无教练邀请</Text>
        ) : (
          pending.map((item) => (
            <View key={item.id} className='coach-invite__card'>
              <Text className='coach-invite__name'>
                {item.coach?.display_name || item.coach?.nickname || '教练'}
              </Text>
              {item.invite_message ? (
                <Text className='coach-invite__message'>{item.invite_message}</Text>
              ) : null}
              <View className='coach-invite__actions'>
                <Button
                  className='coach-invite__accept'
                  loading={actingId === item.id}
                  disabled={actingId === item.id}
                  onClick={() => void accept(item.id)}
                >
                  接受
                </Button>
                <Button
                  className='coach-invite__reject'
                  disabled={actingId === item.id}
                  onClick={() => void reject(item.id)}
                >
                  拒绝
                </Button>
              </View>
            </View>
          ))
        )}
      </View>
    </View>
  )
}

export default CoachInvitePage
