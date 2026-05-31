/**
 * P2-M13-09 · 约球首次强提醒弹窗（不可点遮罩关闭）。
 */

import { FC, useEffect, useState } from 'react'
import { View, Text, Button } from '@tarojs/components'
import Taro from '@tarojs/taro'
import {
  MEETUP_GENDER_OPTIONS,
  meetupSafetyService,
  type MeetupGenderPreference,
  type MeetupTosContent,
} from '@/services/meetupSafetyService'
import { handleMeetupGateError } from '@/utils/meetupGate'
import './MeetupTosModal.scss'

export interface MeetupTosModalProps {
  visible: boolean
  onAccepted: () => void
  onRejected: () => void
  /** 未实名时回调（由父级跳转实名页） */
  onIdentityRequired?: () => void
}

export const MeetupTosModal: FC<MeetupTosModalProps> = ({
  visible,
  onAccepted,
  onRejected,
  onIdentityRequired,
}) => {
  const [tos, setTos] = useState<MeetupTosContent | null>(null)
  const [preference, setPreference] = useState<MeetupGenderPreference>('any')
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (!visible) return
    void (async () => {
      try {
        const [content, status] = await Promise.all([
          meetupSafetyService.getTos(),
          meetupSafetyService.status(),
        ])
        setTos(content)
        setPreference(status.gender_preference)
        if (!status.identity_eligible) {
          onIdentityRequired?.()
        }
      } catch (e) {
        Taro.showToast({
          title: e instanceof Error ? e.message : '加载协议失败',
          icon: 'none',
        })
      }
    })()
  }, [visible])

  if (!visible) return null

  const onAgree = async () => {
    setSubmitting(true)
    try {
      await meetupSafetyService.acceptTos(preference)
      onAccepted()
    } catch (e) {
      if (await handleMeetupGateError(e, { onTosRequired: () => undefined })) {
        onIdentityRequired?.()
        return
      }
      Taro.showToast({
        title: e instanceof Error ? e.message : '同意失败',
        icon: 'none',
      })
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <View className='meetup-tos-modal'>
      <View className='meetup-tos-modal__panel'>
        <Text className='meetup-tos-modal__title'>
          {tos?.title || '约球功能服务须知'}
        </Text>
        <Text className='meetup-tos-modal__body'>
          {tos?.body ||
            '平台仅做信息匹配，不参与线下活动，不承担线下责任。请勿交换联系方式或组织现金对赌。'}
        </Text>
        <Text className='meetup-tos-modal__disclaimer'>
          {tos?.disclaimer || '拒绝将无法使用约球功能。'}
        </Text>

        <View className='meetup-tos-modal__prefs'>
          <Text className='meetup-tos-modal__pref-label'>匹配偏好</Text>
          {MEETUP_GENDER_OPTIONS.map((opt) => (
            <View
              key={opt.value}
              className={[
                'meetup-tos-modal__pref-item',
                preference === opt.value ? 'meetup-tos-modal__pref-item--active' : '',
              ]
                .filter(Boolean)
                .join(' ')}
              onClick={() => setPreference(opt.value)}
            >
              <Text>{opt.label}</Text>
            </View>
          ))}
        </View>

        <View className='meetup-tos-modal__actions'>
          <Button
            className='meetup-tos-modal__btn'
            loading={submitting}
            disabled={submitting}
            onClick={() => void onAgree()}
          >
            同意并继续
          </Button>
          <Button className='meetup-tos-modal__btn-secondary' onClick={onRejected}>
            拒绝
          </Button>
        </View>
      </View>
    </View>
  )
}

export default MeetupTosModal
