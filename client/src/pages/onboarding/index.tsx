import { CSSProperties, FC, useMemo, useState } from 'react'
import { View, Text, Button } from '@tarojs/components'
import Taro from '@tarojs/taro'
import { getSafeAreaInsets } from '@/adapters/safeArea'
import { PHASE2_PROFILE_V2_ENABLED_FLAG } from '@/constants/flags'
import { describeIntermittentRequestFailure, isRequestError } from '@/services/request'
import { useUserStore } from '@/store/userStore'
import { userService } from '@/services/userService'
import { FREQS, GOALS, LEVELS, MAX_GOALS } from '@/constants/golf'
import type { GolfLevel, PrimaryGoal, WeeklyFreq } from '@/types/api'
import { OnboardingV2Flow } from './OnboardingV2Flow'
import './index.scss'

type Step = 1 | 2 | 3
const TOTAL_STEPS = 3

const OnboardingPage: FC = () => {
  const fetchMe = useUserStore((s) => s.fetchMe)
  const [step, setStep] = useState<Step>(1)
  const [level, setLevel] = useState<GolfLevel | null>(null)
  const [goals, setGoals] = useState<PrimaryGoal[]>([])
  const [freq, setFreq] = useState<WeeklyFreq | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [skipping, setSkipping] = useState(false)

  const toggleGoal = (g: PrimaryGoal) => {
    setGoals((prev) =>
      prev.includes(g)
        ? prev.filter((x) => x !== g)
        : prev.length >= MAX_GOALS
          ? prev
          : [...prev, g]
    )
  }

  const canGoNext =
    (step === 1 && !!level) ||
    (step === 2 && goals.length > 0) ||
    (step === 3 && !!freq)

  const handlePrev = () => {
    if (step > 1) setStep(((step - 1) as Step))
  }

  const handleNext = () => {
    if (!canGoNext) return
    if (step < TOTAL_STEPS) setStep(((step + 1) as Step))
  }

  const handleSubmit = async () => {
    if (!level || !freq || goals.length === 0) return
    setSubmitting(true)
    try {
      await userService.completeOnboarding({
        golf_level: level,
        primary_goals: goals,
        weekly_practice_frequency: freq
      })
      await fetchMe()
      Taro.reLaunch({ url: '/pages/index/index' })
    } catch (e) {
      console.warn('onboarding failed', e)
      const title =
        isRequestError(e) && e.kind === 'business' && e.message?.trim()
          ? e.message.trim().slice(0, 220)
          : describeIntermittentRequestFailure(e).toastTitle
      Taro.showToast({
        title,
        icon: 'none',
      })
      setSubmitting(false)
    }
  }

  /**
   * 跳过引导：仅把 onboarding_completed 置为 true，不写入具体档案。
   * 走 PATCH /users/me（后端该接口允许把该字段从 false 置为 true）。
   * 用户之后可以在"我的 · 编辑档案"里再补。
   */
  const handleSkip = () => {
    Taro.showModal({
      title: '跳过档案？',
      content: '你可以在"我的 · 我的画像"里随时补填，AI 教练会更懂你。',
      confirmText: '确认跳过',
      cancelText: '继续填写',
      success: async ({ confirm }) => {
        if (!confirm) return
        setSkipping(true)
        try {
          await userService.updateMe({ onboarding_completed: true })
          await fetchMe()
          Taro.reLaunch({ url: '/pages/index/index' })
        } catch (e) {
          console.warn('skip onboarding failed', e)
          const title =
            isRequestError(e) && e.kind === 'business' && e.message?.trim()
              ? e.message.trim().slice(0, 220)
              : describeIntermittentRequestFailure(e).toastTitle
          Taro.showToast({
            title,
            icon: 'none',
          })
          setSkipping(false)
        }
      },
    })
  }

  const pagePad = useMemo(() => {
    if (process.env.TARO_ENV !== 'rn') return undefined
    const inset = getSafeAreaInsets()
    return {
      paddingTop: inset.top + 14,
      paddingBottom: inset.bottom + 24,
    } as CSSProperties
  }, [])

  if (PHASE2_PROFILE_V2_ENABLED_FLAG) {
    return <OnboardingV2Flow onSkip={handleSkip} skipping={skipping} />
  }

  const nextDisabled = !canGoNext
  const submitDisabled = !canGoNext || submitting

  const renderOption = (
    key: string,
    label: string,
    active: boolean,
    onClick: () => void,
    desc?: string,
  ) => (
    <View
      key={key}
      className={`onboarding__option ${active ? 'onboarding__option--active' : ''}`}
      onClick={onClick}
    >
      <View
        className={`onboarding__option-bar ${active ? 'onboarding__option-bar--active' : ''}`}
      />
      <View className='onboarding__option-body'>
        <Text className='onboarding__option-label'>{label}</Text>
        {desc ? <Text className='onboarding__option-desc'>{desc}</Text> : null}
      </View>
    </View>
  )

  return (
    <View className='onboarding' style={pagePad}>
      {/* 顶部：进度条 + 跳过 */}
      <View className='onboarding__header'>
        <View className='onboarding__progress'>
          <View className='onboarding__progress-bar'>
            <View
              className='onboarding__progress-fill'
              style={{ width: `${(step / TOTAL_STEPS) * 100}%` }}
            />
          </View>
          <Text className='onboarding__progress-text'>
            {step} / {TOTAL_STEPS}
          </Text>
        </View>
        <Text
          className={`onboarding__skip ${skipping ? 'onboarding__skip--disabled' : ''}`}
          onClick={skipping ? undefined : handleSkip}
        >
          {skipping ? '跳过中…' : '跳过'}
        </Text>
      </View>

      {step === 1 && (
        <View className='onboarding__step'>
          <Text className='onboarding__title'>你的高尔夫水平？</Text>
          <View className='onboarding__options'>
            {LEVELS.map((l) =>
              renderOption(l.value, l.label, level === l.value, () => setLevel(l.value), l.desc),
            )}
          </View>
        </View>
      )}

      {step === 2 && (
        <View className='onboarding__step'>
          <Text className='onboarding__title'>主要目标？（最多 {MAX_GOALS} 个）</Text>
          <View className='onboarding__options'>
            {GOALS.map((g) =>
              renderOption(g.value, g.label, goals.includes(g.value), () => toggleGoal(g.value)),
            )}
          </View>
        </View>
      )}

      {step === 3 && (
        <View className='onboarding__step'>
          <Text className='onboarding__title'>练习频率？</Text>
          <View className='onboarding__options'>
            {FREQS.map((f) =>
              renderOption(f.value, f.label, freq === f.value, () => setFreq(f.value)),
            )}
          </View>
        </View>
      )}

      <View className='onboarding__footer'>
        {step > 1 && (
          <Button
            className='onboarding__btn onboarding__btn--ghost'
            onClick={handlePrev}
            disabled={submitting}
          >
            <Text className='onboarding__btn-label onboarding__btn-label--ghost'>上一步</Text>
          </Button>
        )}
        {step < TOTAL_STEPS ? (
          <Button
            className={`onboarding__btn ${nextDisabled ? 'onboarding__btn--disabled' : ''}`}
            disabled={nextDisabled}
            onClick={handleNext}
          >
            <Text
              className={`onboarding__btn-label ${nextDisabled ? 'onboarding__btn-label--disabled' : ''}`}
            >
              下一步
            </Text>
          </Button>
        ) : (
          <Button
            className={`onboarding__btn ${submitDisabled ? 'onboarding__btn--disabled' : ''}`}
            loading={submitting}
            disabled={submitDisabled}
            onClick={handleSubmit}
          >
            <Text
              className={`onboarding__btn-label ${submitDisabled ? 'onboarding__btn-label--disabled' : ''}`}
            >
              完成
            </Text>
          </Button>
        )}
      </View>
    </View>
  )
}

export default OnboardingPage
