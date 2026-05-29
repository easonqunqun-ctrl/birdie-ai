/**
 * P2-M13-05 · 约球邀请详情（接受 / 拒绝 / 撤回）
 */

import { FC, useCallback, useMemo, useState } from 'react'
import { View, Text, Textarea, Button } from '@tarojs/components'
import Taro, { useDidShow, useRouter } from '@tarojs/taro'
import { PHASE2_MEETUP_ENABLED_FLAG } from '@/constants/flags'
import { INVITATION_STATUS_LABEL } from '@/constants/meetup'
import { meetupService, type MeetupInvitationRead } from '@/services/meetupService'
import {
  meetupFeedbackService,
  type MeetupFeedbackEligibility,
} from '@/services/meetupFeedbackService'
import { useUserStore } from '@/store/userStore'
import './detail.scss'

function formatWhen(iso: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}/${d.getMonth() + 1}/${d.getDate()} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

const MeetupDetailPage: FC = () => {
  const router = useRouter()
  const invitationId = router.params.id ?? ''
  const userId = useUserStore((s) => s.user?.id)
  const [loading, setLoading] = useState(true)
  const [acting, setActing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [item, setItem] = useState<MeetupInvitationRead | null>(null)
  const [acceptNote, setAcceptNote] = useState('')
  const [acceptMeetAt, setAcceptMeetAt] = useState('')
  const [feedbackElig, setFeedbackElig] = useState<MeetupFeedbackEligibility | null>(
    null,
  )

  const load = useCallback(async () => {
    if (!invitationId) {
      setError('缺少邀请 ID')
      setLoading(false)
      return
    }
    setLoading(true)
    setError(null)
    try {
      const res = await meetupService.listInvitations({ role: 'any', limit: 100 })
      const found = res.items.find((row) => row.id === invitationId) ?? null
      if (!found) {
        setError('邀请不存在或无权查看')
        setItem(null)
      } else {
        setItem(found)
        if (found.status === 'accepted') {
          try {
            const elig = await meetupFeedbackService.eligibility(found.id)
            setFeedbackElig(elig)
          } catch {
            setFeedbackElig(null)
          }
        } else {
          setFeedbackElig(null)
        }
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }, [invitationId])

  useDidShow(() => {
    if (!PHASE2_MEETUP_ENABLED_FLAG) {
      Taro.navigateBack()
      return
    }
    void load()
  })

  const isInviter = useMemo(
    () => Boolean(item && userId && item.inviter_user_id === userId),
    [item, userId],
  )
  const isInvitee = useMemo(
    () => Boolean(item && userId && item.invitee_user_id === userId),
    [item, userId],
  )
  const canAccept = item?.status === 'pending' && isInvitee
  const canDecline = item?.status === 'pending' && isInvitee
  const canCancel = item?.status === 'pending' && isInviter

  const canFeedback =
    item?.status === 'accepted' &&
    feedbackElig &&
    (feedbackElig.can_submit || feedbackElig.has_submitted)

  const refreshItem = (next: MeetupInvitationRead) => {
    setItem(next)
  }

  const handleAccept = async () => {
    if (!item) return
    setActing(true)
    try {
      const next = await meetupService.acceptInvitation(item.id, {
        note: acceptNote.trim() || null,
        meet_at: acceptMeetAt.trim() || null,
      })
      refreshItem(next)
      Taro.showToast({ title: '已接受', icon: 'success' })
    } catch {
      /* toast by http */
    } finally {
      setActing(false)
    }
  }

  const handleDecline = async () => {
    if (!item) return
    const res = await Taro.showModal({
      title: '拒绝邀请',
      content: '确认拒绝这次约球？',
      confirmText: '拒绝',
      confirmColor: '#ef4444',
    })
    if (!res.confirm) return
    setActing(true)
    try {
      const next = await meetupService.declineInvitation(item.id)
      refreshItem(next)
      Taro.showToast({ title: '已拒绝', icon: 'none' })
    } catch {
      /* toast by http */
    } finally {
      setActing(false)
    }
  }

  const handleCancel = async () => {
    if (!item) return
    const res = await Taro.showModal({
      title: '撤回邀请',
      content: '确认撤回这次约球邀请？',
      confirmText: '撤回',
    })
    if (!res.confirm) return
    setActing(true)
    try {
      const next = await meetupService.cancelInvitation(item.id)
      refreshItem(next)
      Taro.showToast({ title: '已撤回', icon: 'success' })
    } catch {
      /* toast by http */
    } finally {
      setActing(false)
    }
  }

  if (loading) {
    return (
      <View className='meetup-detail meetup-detail--empty'>
        <Text>加载中…</Text>
      </View>
    )
  }

  if (error || !item) {
    return (
      <View className='meetup-detail meetup-detail--empty'>
        <Text className='meetup-detail__error'>{error ?? '未找到邀请'}</Text>
        <View className='meetup-detail__retry' onClick={() => void load()}>
          <Text>重试</Text>
        </View>
      </View>
    )
  }

  return (
    <View className='meetup-detail'>
      <View className='meetup-detail__card'>
        <Text className='meetup-detail__status'>{INVITATION_STATUS_LABEL[item.status]}</Text>
        <View className='meetup-detail__row'>
          <Text className='meetup-detail__label'>约定时间</Text>
          <Text className='meetup-detail__value'>{formatWhen(item.proposed_time)}</Text>
        </View>
        <View className='meetup-detail__row'>
          <Text className='meetup-detail__label'>过期时间</Text>
          <Text className='meetup-detail__value'>{formatWhen(item.expires_at)}</Text>
        </View>
        <View className='meetup-detail__row'>
          <Text className='meetup-detail__label'>我的角色</Text>
          <Text className='meetup-detail__value'>
            {isInviter ? '邀请人' : isInvitee ? '被邀请人' : '—'}
          </Text>
        </View>
        {item.accepted_at && (
          <View className='meetup-detail__row'>
            <Text className='meetup-detail__label'>接受时间</Text>
            <Text className='meetup-detail__value'>{formatWhen(item.accepted_at)}</Text>
          </View>
        )}
        {item.contact_payload && (
          <View className='meetup-detail__contact'>
            <Text className='meetup-detail__contact-title'>会面信息</Text>
            {item.contact_payload.meet_at && (
              <Text className='meetup-detail__contact-line'>
                碰面：{item.contact_payload.meet_at}
              </Text>
            )}
            {item.contact_payload.note && (
              <Text className='meetup-detail__contact-line'>{item.contact_payload.note}</Text>
            )}
          </View>
        )}
      </View>

      {canAccept && (
        <View className='meetup-detail__form'>
          <Text className='meetup-detail__form-title'>接受时可补充会面信息（勿填手机号）</Text>
          <Text className='meetup-detail__field-label'>碰面地点说明</Text>
          <Textarea
            className='meetup-detail__textarea'
            value={acceptMeetAt}
            maxlength={80}
            placeholder='例如：练习场门口'
            onInput={(e) => setAcceptMeetAt(e.detail.value)}
          />
          <Text className='meetup-detail__field-label'>备注</Text>
          <Textarea
            className='meetup-detail__textarea'
            value={acceptNote}
            maxlength={200}
            placeholder='例如：我 7 点到，穿蓝色 Polo'
            onInput={(e) => setAcceptNote(e.detail.value)}
          />
        </View>
      )}

      <View className='meetup-detail__actions'>
        {canAccept && (
          <Button
            className='meetup-detail__btn meetup-detail__btn--primary'
            loading={acting}
            disabled={acting}
            onClick={() => void handleAccept()}
          >
            接受邀请
          </Button>
        )}
        {canDecline && (
          <Button
            className='meetup-detail__btn meetup-detail__btn--ghost'
            loading={acting}
            disabled={acting}
            onClick={() => void handleDecline()}
          >
            拒绝
          </Button>
        )}
        {canCancel && (
          <Button
            className='meetup-detail__btn meetup-detail__btn--ghost'
            loading={acting}
            disabled={acting}
            onClick={() => void handleCancel()}
          >
            撤回邀请
          </Button>
        )}
        {canFeedback && (
          <Button
            className='meetup-detail__btn meetup-detail__btn--primary'
            onClick={() =>
              Taro.navigateTo({
                url: `/pages/meetup/feedback?invitationId=${encodeURIComponent(item.id)}`,
              })
            }
          >
            {feedbackElig?.has_submitted ? '查看互评' : '去评价'}
          </Button>
        )}
      </View>
    </View>
  )
}

export default MeetupDetailPage
