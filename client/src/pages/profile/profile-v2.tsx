/**
 * P2-M9-03 · 画像 2.0 编辑页（GET/PUT profile-v2）
 */

import { FC, useCallback, useState } from 'react'
import { View, Text, Button, Input } from '@tarojs/components'
import Taro, { useDidShow } from '@tarojs/taro'
import { GOALS, GOAL_LABEL, MAX_GOALS } from '@/constants/golf'
import { PHASE2_PROFILE_V2_ENABLED_FLAG } from '@/constants/flags'
import {
  HANDICAP_RANGES,
  HANDICAP_SOURCES,
  HANDEDNESS_OPTIONS,
  INJURY_OPTIONS,
  TRAINING_PREFERENCE_OPTIONS,
  WEEKLY_TARGET_OPTIONS,
  type HandednessOption,
  type HandicapSource,
  type InjuryKey,
} from '@/constants/profileV2'
import { profileV2Service } from '@/services/profileV2'
import {
  goalsFromMidLongLabels,
  handicapRangeIdFromSelf,
} from '@/utils/profileV2Mapping'
import type { PrimaryGoal } from '@/types/api'
import './profile-v2.scss'

const ProfileV2Page: FC = () => {
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [handicapRangeId, setHandicapRangeId] = useState<string | null>(null)
  const [handicapSource, setHandicapSource] = useState<HandicapSource>('self')
  const [handedness, setHandedness] = useState<HandednessOption | null>(null)
  const [heightCm, setHeightCm] = useState('')
  const [weightKg, setWeightKg] = useState('')
  const [injuries, setInjuries] = useState<InjuryKey[]>([])
  const [goals, setGoals] = useState<PrimaryGoal[]>([])
  const [trainingPref, setTrainingPref] = useState<'video' | 'text' | 'mixed' | null>(null)
  const [weeklySessions, setWeeklySessions] = useState<number | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const p = await profileV2Service.get()
      setHandicapRangeId(handicapRangeIdFromSelf(p.handicap_self))
      setHandicapSource(p.handicap_source ?? 'self')
      setHandedness(p.handedness)
      setHeightCm(p.height_cm != null ? String(p.height_cm) : '')
      setWeightKg(p.weight_kg != null ? String(p.weight_kg) : '')
      setInjuries((p.known_injuries ?? []) as InjuryKey[])
      setGoals(goalsFromMidLongLabels(p.mid_long_goals ?? []))
      setTrainingPref(p.training_preference)
      setWeeklySessions(p.weekly_target_sessions)
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }, [])

  useDidShow(() => {
    if (!PHASE2_PROFILE_V2_ENABLED_FLAG) {
      Taro.showToast({ title: '该功能尚未开放', icon: 'none' })
      setTimeout(() => Taro.navigateBack({ delta: 1 }), 1200)
      return
    }
    void load()
  })

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

  const confirmInjuriesIfNeeded = async (): Promise<boolean> => {
    if (injuries.length === 0) return true
    const res = await Taro.showModal({
      title: '保存伤病信息',
      content: '伤病信息仅用于训练建议，不会发送给外部 AI。确认保存？',
      confirmText: '确认',
    })
    return res.confirm
  }

  const handleSave = async () => {
    const range = HANDICAP_RANGES.find((r) => r.id === handicapRangeId)
    if (!range || !handedness || !trainingPref || weeklySessions === null) {
      Taro.showToast({ title: '请补全必填项', icon: 'none' })
      return
    }
    if (goals.length === 0) {
      Taro.showToast({ title: '请至少选择一个目标', icon: 'none' })
      return
    }
    if (!(await confirmInjuriesIfNeeded())) return

    setSaving(true)
    try {
      await profileV2Service.update({
        handicap_self: range.value,
        handicap_source: handicapSource,
        handedness,
        height_cm: heightCm ? Number(heightCm) : null,
        weight_kg: weightKg ? Number(weightKg) : null,
        known_injuries: injuries,
        mid_long_goals: goals.map((g) => GOAL_LABEL[g]),
        training_preference: trainingPref,
        weekly_target_sessions: weeklySessions,
      })
      Taro.showToast({ title: '已保存', icon: 'success' })
      setTimeout(() => Taro.navigateBack(), 600)
    } catch {
      /* toast by http */
    } finally {
      setSaving(false)
    }
  }

  if (!PHASE2_PROFILE_V2_ENABLED_FLAG) {
    return (
      <View className='profile-v2 profile-v2--blocked'>
        <Text>功能维护中…</Text>
      </View>
    )
  }

  if (loading) {
    return (
      <View className='profile-v2 profile-v2--empty'>
        <Text>加载中…</Text>
      </View>
    )
  }

  if (error) {
    return (
      <View className='profile-v2 profile-v2--empty'>
        <Text className='profile-v2__error'>{error}</Text>
        <View className='profile-v2__retry' onClick={() => void load()}>
          <Text>重试</Text>
        </View>
      </View>
    )
  }

  return (
    <View className='profile-v2'>
      <View className='profile-v2__section'>
        <Text className='profile-v2__section-title'>差点水平</Text>
        <View className='profile-v2__options'>
          {HANDICAP_RANGES.map((r) => (
            <View
              key={r.id}
              className={[
                'profile-v2__chip',
                handicapRangeId === r.id ? 'profile-v2__chip--active' : '',
              ]
                .filter(Boolean)
                .join(' ')}
              onClick={() => setHandicapRangeId(r.id)}
            >
              <Text>{r.label}</Text>
            </View>
          ))}
        </View>
        <View className='profile-v2__options'>
          {HANDICAP_SOURCES.map((s) => (
            <View
              key={s.id}
              className={[
                'profile-v2__chip',
                handicapSource === s.id ? 'profile-v2__chip--active' : '',
              ]
                .filter(Boolean)
                .join(' ')}
              onClick={() => setHandicapSource(s.id)}
            >
              <Text>{s.label}</Text>
            </View>
          ))}
        </View>
      </View>

      <View className='profile-v2__section'>
        <Text className='profile-v2__section-title'>惯用手</Text>
        <View className='profile-v2__options'>
          {HANDEDNESS_OPTIONS.map((h) => (
            <View
              key={h.id}
              className={[
                'profile-v2__chip',
                handedness === h.id ? 'profile-v2__chip--active' : '',
              ]
                .filter(Boolean)
                .join(' ')}
              onClick={() => setHandedness(h.id)}
            >
              <Text>{h.label}</Text>
            </View>
          ))}
        </View>
      </View>

      <View className='profile-v2__section'>
        <Text className='profile-v2__section-title'>身高与体重</Text>
        <View className='profile-v2__field'>
          <Text className='profile-v2__field-label'>身高（cm）</Text>
          <Input
            className='profile-v2__input'
            type='number'
            value={heightCm}
            onInput={(e) => setHeightCm(e.detail.value)}
          />
        </View>
        <View className='profile-v2__field'>
          <Text className='profile-v2__field-label'>体重（kg）</Text>
          <Input
            className='profile-v2__input'
            type='number'
            value={weightKg}
            onInput={(e) => setWeightKg(e.detail.value)}
          />
        </View>
      </View>

      <View className='profile-v2__section'>
        <Text className='profile-v2__section-title'>伤病注意</Text>
        <Text className='profile-v2__hint'>可多选；留空表示无</Text>
        <View className='profile-v2__options'>
          {INJURY_OPTIONS.map((opt) => (
            <View
              key={opt.id}
              className={[
                'profile-v2__chip',
                injuries.includes(opt.id) ? 'profile-v2__chip--active' : '',
              ]
                .filter(Boolean)
                .join(' ')}
              onClick={() => toggleInjury(opt.id)}
            >
              <Text>{opt.label}</Text>
            </View>
          ))}
        </View>
      </View>

      <View className='profile-v2__section'>
        <Text className='profile-v2__section-title'>训练目标</Text>
        <View className='profile-v2__options'>
          {GOALS.map((g) => (
            <View
              key={g.value}
              className={[
                'profile-v2__chip',
                goals.includes(g.value) ? 'profile-v2__chip--active' : '',
              ]
                .filter(Boolean)
                .join(' ')}
              onClick={() => toggleGoal(g.value)}
            >
              <Text>{g.label}</Text>
            </View>
          ))}
        </View>
      </View>

      <View className='profile-v2__section'>
        <Text className='profile-v2__section-title'>训练偏好</Text>
        <View className='profile-v2__options'>
          {TRAINING_PREFERENCE_OPTIONS.map((opt) => (
            <View
              key={opt.id}
              className={[
                'profile-v2__chip',
                trainingPref === opt.id ? 'profile-v2__chip--active' : '',
              ]
                .filter(Boolean)
                .join(' ')}
              onClick={() => setTrainingPref(opt.id)}
            >
              <Text>{opt.label}</Text>
            </View>
          ))}
        </View>
        <View className='profile-v2__options'>
          {WEEKLY_TARGET_OPTIONS.map((opt) => (
            <View
              key={opt.value}
              className={[
                'profile-v2__chip',
                weeklySessions === opt.value ? 'profile-v2__chip--active' : '',
              ]
                .filter(Boolean)
                .join(' ')}
              onClick={() => setWeeklySessions(opt.value)}
            >
              <Text>{opt.label}</Text>
            </View>
          ))}
        </View>
      </View>

      <View className='profile-v2__footer'>
        <Button
          className='profile-v2__save'
          loading={saving}
          disabled={saving}
          onClick={() => void handleSave()}
        >
          保存画像
        </Button>
      </View>
    </View>
  )
}

export default ProfileV2Page
