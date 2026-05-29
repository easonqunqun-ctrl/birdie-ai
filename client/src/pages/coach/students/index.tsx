/**
 * M8-03 · 教练查看学员列表。
 */

import { FC, useCallback, useEffect, useState } from 'react'
import { View, Text, Button } from '@tarojs/components'
import Taro, { useDidShow } from '@tarojs/taro'
import { PHASE2_COACH_ENABLED_FLAG } from '@/constants/flags'
import { useUserStore } from '@/store/userStore'
import {
  coachStudentsService,
  type CoachStudentRelationRead,
  type CoachStudentStatus,
} from '@/services/coachStudentsService'
import './students.scss'

const STATUS_LABEL: Record<CoachStudentStatus, string> = {
  pending: '待接受',
  active: '进行中',
  paused: '已暂停',
  ended: '已结束',
}

const CoachStudentsPage: FC = () => {
  const currentRole = useUserStore((s) => s.currentRole)
  const [loading, setLoading] = useState(true)
  const [items, setItems] = useState<CoachStudentRelationRead[]>([])

  const load = useCallback(async () => {
    if (!PHASE2_COACH_ENABLED_FLAG || currentRole !== 'coach') {
      setLoading(false)
      return
    }
    setLoading(true)
    try {
      const res = await coachStudentsService.list()
      setItems(res.items)
    } catch (e) {
      Taro.showToast({
        title: e instanceof Error ? e.message : '加载失败',
        icon: 'none',
      })
    } finally {
      setLoading(false)
    }
  }, [currentRole])

  useEffect(() => {
    void load()
  }, [load])

  useDidShow(() => {
    void load()
  })

  if (!PHASE2_COACH_ENABLED_FLAG) {
    return (
      <View className='coach-students coach-students--blocked'>
        <Text>教练功能尚未开放</Text>
      </View>
    )
  }

  if (currentRole !== 'coach') {
    return (
      <View className='coach-students coach-students--blocked'>
        <Text>请先在「我的」页切换教练模式</Text>
      </View>
    )
  }

  return (
    <View className='coach-students'>
      <View className='coach-students__head'>
        <Text className='coach-students__title'>我的学员</Text>
        <Button
          className='coach-students__invite-btn'
          onClick={() => Taro.navigateTo({ url: '/pages/coach/students-invite' })}
        >
          邀请学员
        </Button>
      </View>

      {loading && (
        <View className='coach-students__empty'>
          <Text>加载中…</Text>
        </View>
      )}

      {!loading && items.length === 0 && (
        <View className='coach-students__empty'>
          <Text>暂无学员</Text>
          <Text className='coach-students__hint'>发送邀请，建立师生关系后开始带练</Text>
        </View>
      )}

      {!loading &&
        items.map((item) => (
          <View key={item.id} className='coach-students__card'>
            <View className='coach-students__card-top'>
              <Text className='coach-students__name'>
                {item.student?.nickname || item.student_user_id}
              </Text>
              <Text className='coach-students__status'>{STATUS_LABEL[item.status]}</Text>
            </View>
            {item.invite_message ? (
              <Text className='coach-students__message'>{item.invite_message}</Text>
            ) : null}
          </View>
        ))}
    </View>
  )
}

export default CoachStudentsPage
