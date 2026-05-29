/**
 * M13-10 · 教练查看学员近期约球（去识别对方）。
 */

import { FC, useCallback, useEffect, useState } from 'react'
import { View, Text, ScrollView, Button } from '@tarojs/components'
import Taro, { useRouter } from '@tarojs/taro'
import {
  INVITATION_STATUS_LABEL,
} from '@/constants/meetup'
import { PHASE2_MEETUP_ENABLED_FLAG } from '@/constants/flags'
import {
  coachSpectatorService,
  type CoachSpectatorInvitationRead,
} from '@/services/coachSpectatorService'
import { useUserStore } from '@/store/userStore'
import './student-meetups.scss'

function formatWhen(iso: string | null): string {
  if (!iso) return '时间待定'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getMonth() + 1}/${d.getDate()} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

const CoachStudentMeetupsPage: FC = () => {
  const router = useRouter()
  const studentId = (router.params.studentId || '').trim()
  const user = useUserStore((s) => s.user)
  const canCoach = Boolean(user?.can_coach_annotate)

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [items, setItems] = useState<CoachSpectatorInvitationRead[]>([])

  const load = useCallback(async () => {
    if (!studentId) {
      setLoading(false)
      setError('缺少学员 ID')
      return
    }
    setLoading(true)
    setError(null)
    try {
      const res = await coachSpectatorService.listStudentMeetups(studentId, {
        page: 1,
        page_size: 30,
      })
      setItems(res.items)
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }, [studentId])

  useEffect(() => {
    if (!PHASE2_MEETUP_ENABLED_FLAG || !canCoach) {
      setLoading(false)
      return
    }
    void load()
  }, [canCoach, load])

  const inviteStudent = () => {
    if (!studentId) return
    Taro.navigateTo({
      url: `/pages/meetup/create?invitee_user_id=${encodeURIComponent(studentId)}`,
    })
  }

  if (!PHASE2_MEETUP_ENABLED_FLAG || !canCoach) {
    return (
      <View className='coach-student-meetups coach-student-meetups--empty'>
        <Text>该功能尚未开放</Text>
      </View>
    )
  }

  return (
    <View className='coach-student-meetups'>
      <View className='coach-student-meetups__head'>
        <Text className='coach-student-meetups__title'>学员近期约球</Text>
        <Text className='coach-student-meetups__meta'>
          对方球友信息已去识别；可邀请学员一起练球
        </Text>
      </View>

      {loading && (
        <View className='coach-student-meetups__empty'>
          <Text>加载中…</Text>
        </View>
      )}

      {!loading && error && (
        <View className='coach-student-meetups__empty'>
          <Text className='coach-student-meetups__error'>{error}</Text>
          <View className='coach-student-meetups__retry' onClick={() => void load()}>
            <Text>重试</Text>
          </View>
        </View>
      )}

      {!loading && !error && items.length === 0 && (
        <View className='coach-student-meetups__empty'>
          <Text>暂无约球记录</Text>
          <Text className='coach-student-meetups__hint'>
            学员授权旁观后，其发起的约球会显示在这里
          </Text>
        </View>
      )}

      {!loading && !error && items.length > 0 && (
        <ScrollView scrollY className='coach-student-meetups__scroll'>
          {items.map((it) => (
            <View key={it.id} className='coach-student-meetups__card'>
              <View className='coach-student-meetups__card-top'>
                <Text className='coach-student-meetups__role'>
                  {it.student_role === 'inviter' ? '学员发起' : '学员收到'}
                </Text>
                <Text className='coach-student-meetups__status'>
                  {INVITATION_STATUS_LABEL[it.status]}
                </Text>
              </View>
              <Text className='coach-student-meetups__time'>{formatWhen(it.proposed_time)}</Text>
              <Text className='coach-student-meetups__meta'>
                创建于 {formatWhen(it.created_at)}
              </Text>
            </View>
          ))}
        </ScrollView>
      )}

      <Button className='coach-student-meetups__action' onClick={inviteStudent}>
        邀请学员练球
      </Button>
    </View>
  )
}

export default CoachStudentMeetupsPage
