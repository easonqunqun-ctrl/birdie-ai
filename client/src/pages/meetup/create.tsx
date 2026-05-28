/**
 * P2-M13-05 · 发起约球（被邀请人 id 经路由 `invitee` 传入）
 */

import { FC, useState } from 'react'
import { View, Text, Textarea, Button, Picker } from '@tarojs/components'
import Taro, { useRouter } from '@tarojs/taro'
import { PHASE2_MEETUP_ENABLED_FLAG } from '@/constants/flags'
import { meetupService } from '@/services/meetupService'
import './create.scss'

const MeetupCreatePage: FC = () => {
  const router = useRouter()
  const inviteeUserId = (router.params.invitee ?? '').trim()
  const [message, setMessage] = useState('')
  const [dateValue, setDateValue] = useState('')
  const [timeValue, setTimeValue] = useState('18:00')
  const [submitting, setSubmitting] = useState(false)

  const buildProposedTime = (): string | null => {
    if (!dateValue) return null
    const iso = `${dateValue}T${timeValue}:00`
    const d = new Date(iso)
    return Number.isNaN(d.getTime()) ? null : d.toISOString()
  }

  const handleSubmit = async () => {
    if (!PHASE2_MEETUP_ENABLED_FLAG) return
    if (!inviteeUserId) {
      Taro.showToast({
        title: '请从球友主页发起，或携带 invitee 参数',
        icon: 'none',
      })
      return
    }
    setSubmitting(true)
    try {
      const inv = await meetupService.createInvitation({
        invitee_user_id: inviteeUserId,
        message: message.trim() || null,
        proposed_time: buildProposedTime(),
      })
      Taro.showToast({ title: '邀请已发送', icon: 'success' })
      setTimeout(() => {
        Taro.redirectTo({
          url: `/pages/meetup/detail?id=${encodeURIComponent(inv.id)}`,
        })
      }, 600)
    } catch {
      /* toast by http */
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <View className='meetup-create'>
      {!inviteeUserId && (
        <View className='meetup-create__warn'>
          <Text>
            当前未指定被邀请球友。完整「选好友」能力将在后续版本提供；测试时可从链接带入
            invitee 用户 ID。
          </Text>
        </View>
      )}

      {inviteeUserId && (
        <View className='meetup-create__row'>
          <Text className='meetup-create__label'>被邀请人</Text>
          <Text className='meetup-create__value meetup-create__value--mono'>
            {inviteeUserId}
          </Text>
        </View>
      )}

      <Text className='meetup-create__field-label'>留言（可选）</Text>
      <Textarea
        className='meetup-create__textarea'
        value={message}
        maxlength={200}
        placeholder='一起练球吗？'
        onInput={(e) => setMessage(e.detail.value)}
      />

      <Text className='meetup-create__field-label'>日期（可选）</Text>
      <Picker mode='date' value={dateValue} onChange={(e) => setDateValue(e.detail.value)}>
        <View className='meetup-create__picker'>
          <Text>{dateValue || '选择日期'}</Text>
        </View>
      </Picker>

      <Text className='meetup-create__field-label'>时间（可选）</Text>
      <Picker mode='time' value={timeValue} onChange={(e) => setTimeValue(e.detail.value)}>
        <View className='meetup-create__picker'>
          <Text>{timeValue}</Text>
        </View>
      </Picker>

      <Button
        className='meetup-create__submit'
        loading={submitting}
        disabled={submitting || !inviteeUserId}
        onClick={() => void handleSubmit()}
      >
        发送邀请
      </Button>
    </View>
  )
}

export default MeetupCreatePage
