/**
 * M8-01 · 教练资质申请页。
 */

import { FC, useCallback, useEffect, useState } from 'react'
import { View, Text, Input, Button, Picker } from '@tarojs/components'
import Taro from '@tarojs/taro'
import { PHASE2_COACH_ENABLED_FLAG } from '@/constants/flags'
import {
  COACH_LEVEL_OPTIONS,
  coachProfileService,
  type CoachProfileRead,
} from '@/services/coachProfileService'
import './apply.scss'

const CoachApplyPage: FC = () => {
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [profile, setProfile] = useState<CoachProfileRead | null>(null)
  const [displayName, setDisplayName] = useState('')
  const [bio, setBio] = useState('')
  const [levelIndex, setLevelIndex] = useState(1)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await coachProfileService.me()
      setProfile(data)
      if (data) {
        setDisplayName(data.display_name)
        setBio(data.bio || '')
        const idx = COACH_LEVEL_OPTIONS.findIndex((o) => o.value === data.level)
        if (idx >= 0) setLevelIndex(idx)
      }
    } catch (e) {
      Taro.showToast({
        title: e instanceof Error ? e.message : '加载失败',
        icon: 'none',
      })
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (!PHASE2_COACH_ENABLED_FLAG) {
      setLoading(false)
      return
    }
    void load()
  }, [load])

  const submit = async () => {
    const name = displayName.trim()
    if (!name) {
      Taro.showToast({ title: '请填写展示名称', icon: 'none' })
      return
    }
    if (profile?.status === 'pending') {
      Taro.showToast({ title: '申请审核中', icon: 'none' })
      return
    }
    if (profile?.status === 'active') {
      Taro.showToast({ title: '您已是认证教练', icon: 'none' })
      return
    }
    setSubmitting(true)
    try {
      await coachProfileService.apply({
        display_name: name,
        level: COACH_LEVEL_OPTIONS[levelIndex].value,
        bio: bio.trim() || undefined,
        materials: [{ type: 'cert_scan', object_key: 'coach-cert/pending-upload' }],
      })
      Taro.showToast({ title: '已提交审核', icon: 'success' })
      await load()
    } catch (e) {
      Taro.showToast({
        title: e instanceof Error ? e.message : '提交失败',
        icon: 'none',
      })
    } finally {
      setSubmitting(false)
    }
  }

  if (!PHASE2_COACH_ENABLED_FLAG) {
    return (
      <View className='coach-apply coach-apply--blocked'>
        <Text>教练功能尚未开放</Text>
      </View>
    )
  }

  const statusLabel =
    profile?.status === 'pending'
      ? '审核中'
      : profile?.status === 'active'
        ? '已认证'
        : profile?.status === 'rejected'
          ? '已驳回，可重新提交'
          : '未申请'

  return (
    <View className='coach-apply'>
      <View className='coach-apply__head'>
        <Text className='coach-apply__title'>教练资质申请</Text>
        <Text className='coach-apply__status'>当前状态：{statusLabel}</Text>
      </View>

      {loading ? (
        <Text className='coach-apply__hint'>加载中…</Text>
      ) : (
        <>
          <View className='coach-apply__field'>
            <Text className='coach-apply__label'>展示名称</Text>
            <Input
              className='coach-apply__input'
              value={displayName}
              maxlength={60}
              onInput={(e) => setDisplayName(e.detail.value)}
            />
          </View>

          <View className='coach-apply__field'>
            <Text className='coach-apply__label'>教练级别</Text>
            <Picker
              mode='selector'
              range={COACH_LEVEL_OPTIONS.map((o) => o.label)}
              value={levelIndex}
              onChange={(e) => setLevelIndex(Number(e.detail.value))}
            >
              <View className='coach-apply__picker'>
                <Text>{COACH_LEVEL_OPTIONS[levelIndex].label}</Text>
              </View>
            </Picker>
          </View>

          <View className='coach-apply__field'>
            <Text className='coach-apply__label'>简介</Text>
            <Input
              className='coach-apply__input coach-apply__input--multiline'
              value={bio}
              maxlength={500}
              onInput={(e) => setBio(e.detail.value)}
            />
          </View>

          <Text className='coach-apply__hint'>
            提交后平台将在 24 小时内完成资质审核；材料上传完整流程将在后续版本开放。
          </Text>

          <Button
            className='coach-apply__submit'
            loading={submitting}
            disabled={submitting || profile?.status === 'pending' || profile?.status === 'active'}
            onClick={() => void submit()}
          >
            提交申请
          </Button>
        </>
      )}
    </View>
  )
}

export default CoachApplyPage
