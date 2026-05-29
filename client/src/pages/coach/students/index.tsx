/**
 * M8-03 / M8-06 · 教练查看学员列表 + 看板指标。
 */

import { FC, useCallback, useEffect, useMemo, useState } from 'react'
import { View, Text, Button } from '@tarojs/components'
import Taro, { useDidShow } from '@tarojs/taro'
import { PHASE2_COACH_ENABLED_FLAG } from '@/constants/flags'
import {
  coachStudentsService,
  type CoachDashboardStudentItem,
  type CoachStudentRelationRead,
  type CoachStudentStatus,
} from '@/services/coachStudentsService'
import { useUserStore } from '@/store/userStore'
import './students.scss'

const STATUS_LABEL: Record<CoachStudentStatus, string> = {
  pending: '待接受',
  active: '进行中',
  paused: '已暂停',
  ended: '已结束',
}

function formatWhen(iso: string | null | undefined): string {
  if (!iso) return '暂无'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const now = new Date()
  const sameDay =
    d.getFullYear() === now.getFullYear() &&
    d.getMonth() === now.getMonth() &&
    d.getDate() === now.getDate()
  const hh = String(d.getHours()).padStart(2, '0')
  const mm = String(d.getMinutes()).padStart(2, '0')
  if (sameDay) return `今天 ${hh}:${mm}`
  const mo = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return `${mo}-${dd} ${hh}:${mm}`
}

const CoachStudentsPage: FC = () => {
  const currentRole = useUserStore((s) => s.currentRole)
  const [loading, setLoading] = useState(true)
  const [pendingItems, setPendingItems] = useState<CoachStudentRelationRead[]>([])
  const [dashboardStudents, setDashboardStudents] = useState<CoachDashboardStudentItem[]>([])
  const [dashboardFallback, setDashboardFallback] = useState<CoachStudentRelationRead[]>([])

  const load = useCallback(async () => {
    if (!PHASE2_COACH_ENABLED_FLAG || currentRole !== 'coach') {
      setLoading(false)
      return
    }
    setLoading(true)
    try {
      const [pendingRes, dashboardRes] = await Promise.all([
        coachStudentsService.list('pending'),
        coachStudentsService.dashboardList().catch(async (e) => {
          if (e instanceof Error && /404|未开放/.test(e.message)) {
            const fallback = await coachStudentsService.list('active')
            setDashboardFallback(fallback.items)
            return null
          }
          throw e
        }),
      ])
      setPendingItems(pendingRes.items)
      if (dashboardRes) {
        setDashboardStudents(dashboardRes.students)
        setDashboardFallback([])
      }
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

  const activeCards = useMemo(() => {
    if (dashboardStudents.length > 0) {
      return dashboardStudents.map((item) => ({
        key: item.relation_id,
        studentUserId: item.student_user_id,
        displayName: item.display_name,
        metrics: item,
      }))
    }
    return dashboardFallback.map((item) => ({
      key: item.id,
      studentUserId: item.student_user_id,
      displayName: item.student?.nickname || item.student_user_id,
      metrics: null as CoachDashboardStudentItem | null,
    }))
  }, [dashboardFallback, dashboardStudents])

  const hasAnyStudents = pendingItems.length > 0 || activeCards.length > 0

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

      {!loading && !hasAnyStudents && (
        <View className='coach-students__empty'>
          <Text>暂无学员</Text>
          <Text className='coach-students__hint'>发送邀请，建立师生关系后开始带练</Text>
        </View>
      )}

      {!loading &&
        pendingItems.map((item) => (
          <View key={item.id} className='coach-students__card coach-students__card--pending'>
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

      {!loading &&
        activeCards.map((card) => (
          <View
            key={card.key}
            className='coach-students__card'
            onClick={() =>
              card.metrics
                ? Taro.navigateTo({
                    url: `/pages/coach/students/detail?studentUserId=${encodeURIComponent(card.studentUserId)}`,
                  })
                : undefined
            }
          >
            <View className='coach-students__card-top'>
              <Text className='coach-students__name'>{card.displayName}</Text>
              {card.metrics?.needs_response ? (
                <Text className='coach-students__badge'>待回应</Text>
              ) : (
                <Text className='coach-students__status'>{STATUS_LABEL.active}</Text>
              )}
            </View>

            {card.metrics ? (
              <View className='coach-students__metrics'>
                <Text className='coach-students__metric'>7 天分析 {card.metrics.analyses_7d}</Text>
                <Text className='coach-students__metric'>
                  待完成 {card.metrics.pending_tasks}
                </Text>
                <Text className='coach-students__metric'>
                  最近 {formatWhen(card.metrics.last_analysis_at)}
                </Text>
              </View>
            ) : null}

            <View className='coach-students__card-actions'>
              {card.metrics ? (
                <Button
                  className='coach-students__action-btn coach-students__action-btn--ghost'
                  onClick={(e) => {
                    e.stopPropagation()
                    Taro.navigateTo({
                      url: `/pages/coach/students/detail?studentUserId=${encodeURIComponent(card.studentUserId)}`,
                    })
                  }}
                >
                  查看看板
                </Button>
              ) : null}
              <Button
                className='coach-students__action-btn'
                onClick={(e) => {
                  e.stopPropagation()
                  Taro.navigateTo({
                    url: `/pages/coach/task-assign/index?studentUserId=${encodeURIComponent(card.studentUserId)}&studentName=${encodeURIComponent(card.displayName)}`,
                  })
                }}
              >
                布置作业
              </Button>
            </View>
          </View>
        ))}
    </View>
  )
}

export default CoachStudentsPage
