/**
 * M8-03 · 教练邀请学员页。
 */

import { FC, useState } from 'react'
import { View, Text, Input, Button } from '@tarojs/components'
import Taro from '@tarojs/taro'
import { PHASE2_COACH_ENABLED_FLAG } from '@/constants/flags'
import { useUserStore } from '@/store/userStore'
import { coachStudentsService } from '@/services/coachStudentsService'
import './students-invite.scss'

const CoachStudentsInvitePage: FC = () => {
  const currentRole = useUserStore((s) => s.currentRole)
  const [inviteCode, setInviteCode] = useState('')
  const [message, setMessage] = useState('')
  const [submitting, setSubmitting] = useState(false)

  if (!PHASE2_COACH_ENABLED_FLAG) {
    return (
      <View className='coach-students-invite coach-students-invite--blocked'>
        <Text>教练功能尚未开放</Text>
      </View>
    )
  }

  if (currentRole !== 'coach') {
    return (
      <View className='coach-students-invite coach-students-invite--blocked'>
        <Text>请先在「我的」页切换教练模式</Text>
      </View>
    )
  }

  const submit = async () => {
    const code = inviteCode.trim().toUpperCase()
    if (!code) {
      Taro.showToast({ title: '请输入学员邀请码', icon: 'none' })
      return
    }
    setSubmitting(true)
    try {
      await coachStudentsService.invite({ invite_code: code, message: message.trim() || undefined })
      Taro.showToast({ title: '邀请已发送', icon: 'success' })
      setInviteCode('')
      setMessage('')
    } catch (e) {
      Taro.showToast({
        title: e instanceof Error ? e.message : '邀请失败',
        icon: 'none',
      })
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <View className='coach-students-invite'>
      <Text className='coach-students-invite__title'>邀请学员</Text>
      <Text className='coach-students-invite__hint'>
        输入学员的邀请码（可在「我的 → 邀请好友」查看），对方接受后建立师生关系。
      </Text>
      <View className='coach-students-invite__field'>
        <Text className='coach-students-invite__label'>学员邀请码</Text>
        <Input
          className='coach-students-invite__input'
          value={inviteCode}
          maxlength={8}
          placeholder='例如 AB12CD34'
          onInput={(e) => setInviteCode((e.detail.value || '').toUpperCase())}
        />
      </View>
      <View className='coach-students-invite__field'>
        <Text className='coach-students-invite__label'>附言（可选）</Text>
        <Input
          className='coach-students-invite__input'
          value={message}
          maxlength={120}
          placeholder='一起练短杆吧'
          onInput={(e) => setMessage(e.detail.value || '')}
        />
      </View>
      <Button
        className='coach-students-invite__btn'
        loading={submitting}
        disabled={submitting}
        onClick={() => void submit()}
      >
        发送邀请
      </Button>
    </View>
  )
}

export default CoachStudentsInvitePage
