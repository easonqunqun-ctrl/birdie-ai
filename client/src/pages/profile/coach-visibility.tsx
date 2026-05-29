/**
 * M8-03 · 学员对教练的字段级可见性。
 */

import { FC, useCallback, useEffect, useState } from 'react'
import { View, Text, Switch } from '@tarojs/components'
import Taro from '@tarojs/taro'
import { PHASE2_COACH_ENABLED_FLAG } from '@/constants/flags'
import {
  COACH_VISIBILITY_FIELDS,
  coachStudentsService,
  type CoachStudentRelationRead,
} from '@/services/coachStudentsService'
import './coach-visibility.scss'

const CoachVisibilityPage: FC = () => {
  const [loading, setLoading] = useState(true)
  const [relation, setRelation] = useState<CoachStudentRelationRead | null>(null)
  const [saving, setSaving] = useState(false)

  const load = useCallback(async () => {
    if (!PHASE2_COACH_ENABLED_FLAG) {
      setLoading(false)
      return
    }
    setLoading(true)
    try {
      const data = await coachStudentsService.myCoachOverview()
      const target = data.active || data.paused
      setRelation(target)
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
    void load()
  }, [load])

  const onToggle = async (key: string, checked: boolean) => {
    if (!relation || saving) return
    setSaving(true)
    try {
      const updated = await coachStudentsService.updateVisibility(relation.id, {
        [key]: checked,
      } as Record<string, boolean>)
      setRelation(updated)
      Taro.showToast({ title: '已更新', icon: 'none' })
    } catch (e) {
      Taro.showToast({
        title: e instanceof Error ? e.message : '更新失败',
        icon: 'none',
      })
    } finally {
      setSaving(false)
    }
  }

  if (!PHASE2_COACH_ENABLED_FLAG) {
    return (
      <View className='coach-visibility coach-visibility--blocked'>
        <Text>教练功能尚未开放</Text>
      </View>
    )
  }

  if (loading) {
    return (
      <View className='coach-visibility coach-visibility--blocked'>
        <Text>加载中…</Text>
      </View>
    )
  }

  if (!relation) {
    return (
      <View className='coach-visibility coach-visibility--blocked'>
        <Text>暂无活跃教练，无法接受可见性设置</Text>
      </View>
    )
  }

  const payload = relation.visibility_payload || {}

  return (
    <View className='coach-visibility'>
      <Text className='coach-visibility__hint'>
        默认所有字段对教练不可见。开启后，教练才可查看对应信息。伤病信息不对教练开放。
      </Text>
      {COACH_VISIBILITY_FIELDS.map((field) => (
        <View key={field.key} className='coach-visibility__row'>
          <View className='coach-visibility__text'>
            <Text className='coach-visibility__label'>{field.label}</Text>
          </View>
          <Switch
            checked={Boolean(payload[field.key])}
            disabled={saving}
            color='var(--color-primary)'
            onChange={(e) => void onToggle(field.key, Boolean(e.detail.value))}
          />
        </View>
      ))}
    </View>
  )
}

export default CoachVisibilityPage
