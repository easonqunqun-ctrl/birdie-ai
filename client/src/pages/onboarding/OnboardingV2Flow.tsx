/**
 * P2-M9-03 · Onboarding 2.0（6 步问卷 → profile-v2 + v1 onboarding 双写）
 */

import { FC, useState } from 'react'
import { View, Text, Button, Input } from '@tarojs/components'
import Taro from '@tarojs/taro'
import { GOALS, GOAL_LABEL, MAX_GOALS } from '@/constants/golf'
import {
  HANDICAP_RANGES,
  HANDICAP_SOURCES,
  HANDEDNESS_OPTIONS,
  HEIGHT_RANGE,
  INJURY_OPTIONS,
  ONBOARDING_V2_TOTAL_STEPS,
  TRAINING_PREFERENCE_OPTIONS,
  WEEKLY_TARGET_OPTIONS,
  WEIGHT_RANGE,
  type HandednessOption,
  type HandicapSource,
  type InjuryKey,
} from '@/constants/profileV2'
import { describeIntermittentRequestFailure, isRequestError } from '@/services/request'
import { profileV2Service } from '@/services/profileV2'
import { userService } from '@/services/userService'
import { useUserStore } from '@/store/userStore'
import {
  mapHandicapSelfToGolfLevel,
  mapWeeklySessionsToFreq,
} from '@/utils/profileV2Mapping'
import type { PrimaryGoal } from '@/types/api'

type Step = 1 | 2 | 3 | 4 | 5 | 6

interface OnboardingV2FlowProps {
  onSkip: () => void
  skipping: boolean
}

export const OnboardingV2Flow: FC<OnboardingV2FlowProps> = ({ onSkip, skipping }) => {
  const fetchMe = useUserStore((s) => s.fetchMe)
  const [step, setStep] = useState<Step>(1)
  const [handicapRangeId, setHandicapRangeId] = useState<string | null>(null)
  const [handicapSource, setHandicapSource] = useState<HandicapSource>('self')
  const [handedness, setHandedness] = useState<HandednessOption | null>(null)
  const [heightCm, setHeightCm] = useState(String(HEIGHT_RANGE.default))
  const [weightKg, setWeightKg] = useState(String(WEIGHT_RANGE.default))
  const [injuries, setInjuries] = useState<InjuryKey[]>([])
  const [goals, setGoals] = useState<PrimaryGoal[]>([])
  const [trainingPref, setTrainingPref] = useState<'video' | 'text' | 'mixed' | null>(null)
  const [weeklySessions, setWeeklySessions] = useState<number | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const toggleInjury = (key: InjuryKey) => {
    setInjuries((prev) =>
      prev.includes(key) ? prev.filter((x) => x !== key) : [...prev, key],
    )
  }

  const toggleGoal = (g: PrimaryGoal) => {
    setGoals((prev) =>
      prev.includes(g)
        ? prev.filter((x) => x !== g)
        : prev.length >= MAX_GOALS
          ? prev
          : [...prev, g],
    )
  }

  const canGoNext = (): boolean => {
    switch (step) {
      case 1:
        return !!handicapRangeId
      case 2:
        return !!handedness
      case 3: {
        const h = Number(heightCm)
        const w = Number(weightKg)
        return (
          Number.isFinite(h) &&
          h >= HEIGHT_RANGE.min &&
          h <= HEIGHT_RANGE.max &&
          Number.isFinite(w) &&
          w >= WEIGHT_RANGE.min &&
          w <= WEIGHT_RANGE.max
        )
      }
      case 4:
        return true
      case 5:
        return goals.length > 0
      case 6:
        return !!trainingPref && weeklySessions !== null
      default:
        return false
    }
  }

  const confirmInjuriesIfNeeded = async (): Promise<boolean> => {
    if (injuries.length === 0) return true
    const res = await Taro.showModal({
      title: '伤病信息说明',
      content:
        '伤病信息仅用于训练建议，不会发送给外部 AI。你可以在「我的画像」中随时修改或清空。',
      confirmText: '我知道了',
    })
    return res.confirm
  }

  const handleNext = async () => {
    if (!canGoNext()) return
    if (step === 4) {
      const ok = await confirmInjuriesIfNeeded()
      if (!ok) return
    }
    if (step < ONBOARDING_V2_TOTAL_STEPS) {
      setStep(((step + 1) as Step))
    }
  }

  const handlePrev = () => {
    if (step > 1) setStep(((step - 1) as Step))
  }

  const handleSubmit = async () => {
    if (!canGoNext()) return
    const range = HANDICAP_RANGES.find((r) => r.id === handicapRangeId)
    if (!range || !handedness || !trainingPref || weeklySessions === null) return

    setSubmitting(true)
    try {
      await profileV2Service.update({
        handicap_self: range.value,
        handicap_source: handicapSource,
        handedness,
        height_cm: Number(heightCm),
        weight_kg: Number(weightKg),
        known_injuries: injuries,
        mid_long_goals: goals.map((g) => GOAL_LABEL[g]),
        training_preference: trainingPref,
        weekly_target_sessions: weeklySessions,
      })
      await userService.completeOnboarding({
        golf_level: mapHandicapSelfToGolfLevel(range.value),
        primary_goals: goals,
        weekly_practice_frequency: mapWeeklySessionsToFreq(weeklySessions),
      })
      await fetchMe()
      Taro.reLaunch({ url: '/pages/index/index' })
    } catch (e) {
      const title =
        isRequestError(e) && e.kind === 'business' && e.message?.trim()
          ? e.message.trim().slice(0, 220)
          : describeIntermittentRequestFailure(e).toastTitle
      Taro.showToast({ title, icon: 'none' })
      setSubmitting(false)
    }
  }

  return (
    <View className='onboarding'>
      <View className='onboarding__header'>
        <View className='onboarding__progress'>
          <View className='onboarding__progress-bar'>
            <View
              className='onboarding__progress-fill'
              style={{ width: `${(step / ONBOARDING_V2_TOTAL_STEPS) * 100}%` }}
            />
          </View>
          <Text className='onboarding__progress-text'>
            {step} / {ONBOARDING_V2_TOTAL_STEPS}
          </Text>
        </View>
        <Text
          className={`onboarding__skip ${skipping ? 'onboarding__skip--disabled' : ''}`}
          onClick={skipping ? undefined : onSkip}
        >
          {skipping ? '跳过中…' : '跳过'}
        </Text>
      </View>

      {step === 1 && (
        <View className='onboarding__step'>
          <Text className='onboarding__title'>你的差点水平？</Text>
          <View className='onboarding__options'>
            {HANDICAP_RANGES.map((r) => (
              <View
                key={r.id}
                className={`onboarding__option ${handicapRangeId === r.id ? 'onboarding__option--active' : ''}`}
                onClick={() => setHandicapRangeId(r.id)}
              >
                <Text className='onboarding__option-label'>{r.label}</Text>
              </View>
            ))}
          </View>
          <Text className='onboarding__sub-title'>差点来源</Text>
          <View className='onboarding__options onboarding__options--compact'>
            {HANDICAP_SOURCES.map((s) => (
              <View
                key={s.id}
                className={`onboarding__option ${handicapSource === s.id ? 'onboarding__option--active' : ''}`}
                onClick={() => setHandicapSource(s.id)}
              >
                <Text className='onboarding__option-label'>{s.label}</Text>
              </View>
            ))}
          </View>
        </View>
      )}

      {step === 2 && (
        <View className='onboarding__step'>
          <Text className='onboarding__title'>惯用手？</Text>
          <View className='onboarding__options'>
            {HANDEDNESS_OPTIONS.map((h) => (
              <View
                key={h.id}
                className={`onboarding__option ${handedness === h.id ? 'onboarding__option--active' : ''}`}
                onClick={() => setHandedness(h.id)}
              >
                <Text className='onboarding__option-label'>{h.label}</Text>
              </View>
            ))}
          </View>
        </View>
      )}

      {step === 3 && (
        <View className='onboarding__step'>
          <Text className='onboarding__title'>身高与体重</Text>
          <Text className='onboarding__hint'>用于推荐更合适的动作幅度（可后续修改）</Text>
          <View className='onboarding__field'>
            <Text className='onboarding__field-label'>身高（cm）</Text>
            <Input
              className='onboarding__input'
              type='number'
              value={heightCm}
              onInput={(e) => setHeightCm(e.detail.value)}
            />
          </View>
          <View className='onboarding__field'>
            <Text className='onboarding__field-label'>体重（kg）</Text>
            <Input
              className='onboarding__input'
              type='number'
              value={weightKg}
              onInput={(e) => setWeightKg(e.detail.value)}
            />
          </View>
        </View>
      )}

      {step === 4 && (
        <View className='onboarding__step'>
          <Text className='onboarding__title'>有需要注意的伤病吗？</Text>
          <Text className='onboarding__hint'>可多选；没有则直接下一步</Text>
          <View className='onboarding__options'>
            {INJURY_OPTIONS.map((opt) => (
              <View
                key={opt.id}
                className={`onboarding__option ${injuries.includes(opt.id) ? 'onboarding__option--active' : ''}`}
                onClick={() => toggleInjury(opt.id)}
              >
                <Text className='onboarding__option-label'>{opt.label}</Text>
              </View>
            ))}
          </View>
        </View>
      )}

      {step === 5 && (
        <View className='onboarding__step'>
          <Text className='onboarding__title'>中长期目标？（最多 {MAX_GOALS} 个）</Text>
          <View className='onboarding__options'>
            {GOALS.map((g) => (
              <View
                key={g.value}
                className={`onboarding__option ${goals.includes(g.value) ? 'onboarding__option--active' : ''}`}
                onClick={() => toggleGoal(g.value)}
              >
                <Text className='onboarding__option-label'>{g.label}</Text>
              </View>
            ))}
          </View>
        </View>
      )}

      {step === 6 && (
        <View className='onboarding__step'>
          <Text className='onboarding__title'>训练偏好</Text>
          <View className='onboarding__options'>
            {TRAINING_PREFERENCE_OPTIONS.map((opt) => (
              <View
                key={opt.id}
                className={`onboarding__option ${trainingPref === opt.id ? 'onboarding__option--active' : ''}`}
                onClick={() => setTrainingPref(opt.id)}
              >
                <Text className='onboarding__option-label'>{opt.label}</Text>
              </View>
            ))}
          </View>
          <Text className='onboarding__sub-title'>每周目标练习次数</Text>
          <View className='onboarding__options'>
            {WEEKLY_TARGET_OPTIONS.map((opt) => (
              <View
                key={opt.value}
                className={`onboarding__option ${weeklySessions === opt.value ? 'onboarding__option--active' : ''}`}
                onClick={() => setWeeklySessions(opt.value)}
              >
                <Text className='onboarding__option-label'>{opt.label}</Text>
              </View>
            ))}
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
            上一步
          </Button>
        )}
        {step < ONBOARDING_V2_TOTAL_STEPS ? (
          <Button
            className='onboarding__btn'
            disabled={!canGoNext()}
            onClick={() => void handleNext()}
          >
            下一步
          </Button>
        ) : (
          <Button
            className='onboarding__btn'
            loading={submitting}
            disabled={!canGoNext() || submitting}
            onClick={() => void handleSubmit()}
          >
            完成
          </Button>
        )}
      </View>
    </View>
  )
}
