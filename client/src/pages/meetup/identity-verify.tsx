/**
 * P2-M13-09 · 约球实名认证页
 */

import { FC, useMemo, useState } from 'react'
import { View, Text, Button, Picker } from '@tarojs/components'
import Taro, { useRouter } from '@tarojs/taro'
import { extractPhoneCodeFromEvent, PhoneAuthError } from '@/adapters/phone'
import MeetupTosModal from '@/components/MeetupTosModal'
import { PHASE2_MEETUP_ENABLED_FLAG } from '@/constants/flags'
import { meetupSafetyService } from '@/services/meetupSafetyService'
import { isRequestError } from '@/services/request'
import {
  handleMeetupGateError,
  showMeetupMinorBlockedModal,
} from '@/utils/meetupGate'
import './identity-verify.scss'

const MIN_MEETUP_AGE = 14

function pad2(n: number): string {
  return String(n).padStart(2, '0')
}

function formatDate(d: Date): string {
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`
}

function parseDate(value: string): Date | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value)
  if (!m) return null
  const d = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]))
  if (Number.isNaN(d.getTime())) return null
  return d
}

function ageYears(birth: Date, on: Date): number {
  let years = on.getFullYear() - birth.getFullYear()
  const md = on.getMonth() - birth.getMonth()
  if (md < 0 || (md === 0 && on.getDate() < birth.getDate())) {
    years -= 1
  }
  return years
}

const MeetupIdentityVerifyPage: FC = () => {
  const router = useRouter()
  const redirect = router.params.redirect
    ? decodeURIComponent(router.params.redirect)
    : ''

  const maxBirthDate = useMemo(() => {
    const d = new Date()
    d.setFullYear(d.getFullYear() - MIN_MEETUP_AGE)
    return formatDate(d)
  }, [])

  const [birthDate, setBirthDate] = useState('')
  const [phoneCode, setPhoneCode] = useState<string | null>(null)
  const [phoneHint, setPhoneHint] = useState('请点击下方按钮授权微信手机号')
  const [submitting, setSubmitting] = useState(false)
  const [showTos, setShowTos] = useState(false)

  const finishSuccess = () => {
    if (redirect) {
      Taro.showToast({ title: '验证成功', icon: 'success' })
      setTimeout(() => {
        void Taro.redirectTo({ url: redirect })
      }, 600)
      return
    }
    Taro.showToast({ title: '验证成功', icon: 'success' })
    setTimeout(() => Taro.navigateBack(), 600)
  }

  const afterVerified = async () => {
    const status = await meetupSafetyService.status()
    if (!status.can_use_meetup) {
      setShowTos(true)
      return
    }
    finishSuccess()
  }

  const handleSubmit = async () => {
    if (!birthDate) {
      Taro.showToast({ title: '请选择出生日期', icon: 'none' })
      return
    }
    const birth = parseDate(birthDate)
    if (!birth) {
      Taro.showToast({ title: '出生日期格式无效', icon: 'none' })
      return
    }
    const today = new Date()
    if (birth > today) {
      Taro.showToast({ title: '出生日期不能晚于今天', icon: 'none' })
      return
    }
    if (ageYears(birth, today) < MIN_MEETUP_AGE) {
      await showMeetupMinorBlockedModal()
      return
    }
    if (!phoneCode) {
      Taro.showToast({ title: '请先授权微信手机号', icon: 'none' })
      return
    }

    setSubmitting(true)
    try {
      await meetupSafetyService.verifyIdentity({
        birth_date: birthDate,
        phone_code: phoneCode,
      })
      await afterVerified()
    } catch (e) {
      if (await handleMeetupGateError(e, { onTosRequired: () => setShowTos(true) })) {
        return
      }
      const msg = isRequestError(e)
        ? e.message
        : e instanceof Error
          ? e.message
          : '验证失败，请稍后重试'
      Taro.showToast({ title: msg, icon: 'none' })
    } finally {
      setSubmitting(false)
    }
  }

  const onGetPhoneNumber = async (e: { detail?: { code?: string; errMsg?: string } }) => {
    try {
      const code = await extractPhoneCodeFromEvent(e.detail)
      setPhoneCode(code)
      setPhoneHint('已授权微信手机号')
    } catch (err) {
      const msg =
        err instanceof PhoneAuthError ? err.message : err instanceof Error ? err.message : '授权失败'
      setPhoneHint(msg)
      Taro.showToast({ title: msg, icon: 'none' })
    }
  }

  if (!PHASE2_MEETUP_ENABLED_FLAG) {
    return (
      <View className='meetup-identity meetup-identity--blocked'>
        <Text>功能维护中…</Text>
      </View>
    )
  }

  return (
    <View className='meetup-identity'>
      <Text className='meetup-identity__title'>约球安全验证</Text>
      <Text className='meetup-identity__desc'>
        使用约球、附近球馆等功能前，需确认您已满 14 周岁并绑定微信手机号。信息仅用于安全合规，不会用于营销。
      </Text>

      <View className='meetup-identity__field'>
        <Text className='meetup-identity__label'>出生日期</Text>
        <Picker
          mode='date'
          value={birthDate || maxBirthDate}
          end={maxBirthDate}
          start='1940-01-01'
          onChange={(e) => setBirthDate(String(e.detail.value))}
        >
          <View className='meetup-identity__picker'>
            <Text>{birthDate || '请选择出生日期'}</Text>
          </View>
        </Picker>
      </View>

      <View className='meetup-identity__field'>
        <Text className='meetup-identity__label'>微信手机号</Text>
        <Text className='meetup-identity__hint'>{phoneHint}</Text>
        <Button
          className='meetup-identity__phone-btn'
          openType='getPhoneNumber'
          onGetPhoneNumber={(e) => void onGetPhoneNumber(e)}
        >
          微信授权手机号
        </Button>
      </View>

      <Button
        className='meetup-identity__submit'
        loading={submitting}
        disabled={submitting}
        onClick={() => void handleSubmit()}
      >
        提交验证
      </Button>

      <MeetupTosModal
        visible={showTos}
        onAccepted={() => {
          setShowTos(false)
          void finishSuccess()
        }}
        onRejected={() => setShowTos(false)}
      />
    </View>
  )
}

export default MeetupIdentityVerifyPage
