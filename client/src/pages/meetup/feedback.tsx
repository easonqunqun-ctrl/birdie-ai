/**
 * P2-M13-07 · 约球互评页。
 */

import { FC, useCallback, useState } from 'react'
import { View, Text, Textarea, Button } from '@tarojs/components'
import Taro, { useDidShow, useRouter } from '@tarojs/taro'
import { PHASE2_MEETUP_ENABLED_FLAG } from '@/constants/flags'
import {
  meetupFeedbackService,
  MEETUP_FEEDBACK_TAG_OPTIONS,
  type MeetupFeedbackRead,
} from '@/services/meetupFeedbackService'
import './feedback.scss'

const MeetupFeedbackPage: FC = () => {
  const router = useRouter()
  const invitationId = (router.params.invitationId || '').trim()

  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [canSubmit, setCanSubmit] = useState(false)
  const [hasSubmitted, setHasSubmitted] = useState(false)
  const [peerVisible, setPeerVisible] = useState(false)
  const [rating, setRating] = useState(5)
  const [tags, setTags] = useState<string[]>([])
  const [comment, setComment] = useState('')
  const [peerFeedback, setPeerFeedback] = useState<MeetupFeedbackRead | null>(null)

  const load = useCallback(async () => {
    if (!invitationId) {
      setLoading(false)
      return
    }
    setLoading(true)
    try {
      const [elig, listed] = await Promise.all([
        meetupFeedbackService.eligibility(invitationId),
        meetupFeedbackService.listForInvitation(invitationId),
      ])
      setCanSubmit(elig.can_submit)
      setHasSubmitted(elig.has_submitted)
      setPeerVisible(elig.peer_visible)
      const peer = listed.items.find((f) => f.reviewer_user_id !== listed.items[0]?.reviewer_user_id)
      setPeerFeedback(peer ?? null)
    } catch (e) {
      Taro.showToast({
        title: e instanceof Error ? e.message : '加载失败',
        icon: 'none',
      })
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

  const toggleTag = (key: string) => {
    setTags((prev) =>
      prev.includes(key) ? prev.filter((t) => t !== key) : [...prev, key],
    )
  }

  const handleSubmit = async () => {
    if (!invitationId || !canSubmit) return
    setSubmitting(true)
    try {
      await meetupFeedbackService.submit({
        invitation_id: invitationId,
        rating,
        tags,
        comment: comment.trim() || null,
      })
      Taro.showToast({ title: '评价已提交', icon: 'success' })
      setHasSubmitted(true)
      setCanSubmit(false)
      setTimeout(() => Taro.navigateBack(), 800)
    } catch {
      /* toast by http */
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) {
    return (
      <View className='meetup-feedback'>
        <Text>加载中…</Text>
      </View>
    )
  }

  return (
    <View className='meetup-feedback'>
      <Text className='meetup-feedback__title'>约球互评</Text>
      <Text className='meetup-feedback__hint'>
        约球结束 24 小时后可评价；提交后 24 小时可查看对方评分。
      </Text>

      {canSubmit && !hasSubmitted && (
        <>
          <View className='meetup-feedback__stars'>
            {[1, 2, 3, 4, 5].map((n) => (
              <View
                key={n}
                className={`meetup-feedback__star ${
                  rating >= n ? 'meetup-feedback__star--active' : ''
                }`}
                onClick={() => setRating(n)}
              >
                <Text>{n}</Text>
              </View>
            ))}
          </View>

          <View className='meetup-feedback__tags'>
            {MEETUP_FEEDBACK_TAG_OPTIONS.map((opt) => (
              <View
                key={opt.key}
                className={`meetup-feedback__tag ${
                  tags.includes(opt.key) ? 'meetup-feedback__tag--active' : ''
                }`}
                onClick={() => toggleTag(opt.key)}
              >
                <Text>{opt.label}</Text>
              </View>
            ))}
          </View>

          <Textarea
            className='meetup-feedback__textarea'
            value={comment}
            maxlength={500}
            placeholder='补充说明（可选）'
            onInput={(e) => setComment(e.detail.value)}
          />

          <Button
            className='meetup-feedback__btn'
            loading={submitting}
            onClick={() => void handleSubmit()}
          >
            提交评价
          </Button>
        </>
      )}

      {hasSubmitted && !peerVisible && (
        <Text className='meetup-feedback__hint'>你已评价，24 小时后可查看对方评分。</Text>
      )}

      {peerVisible && peerFeedback && (
        <View className='meetup-feedback__peer'>
          <Text className='meetup-feedback__peer-title'>对方给你的评价</Text>
          <Text className='meetup-feedback__peer-meta'>
            {peerFeedback.rating} 分 · {peerFeedback.tags.join('、') || '无标签'}
          </Text>
          {peerFeedback.comment && (
            <Text className='meetup-feedback__peer-meta'>{peerFeedback.comment}</Text>
          )}
        </View>
      )}
    </View>
  )
}

export default MeetupFeedbackPage
