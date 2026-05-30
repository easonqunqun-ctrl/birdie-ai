/**
 * M8-05 · 教练向学员派发 drill 作业。
 */

import { FC, useEffect, useMemo, useState } from 'react'
import { View, Text, Button, Picker, Textarea, Input } from '@tarojs/components'
import Taro, { useRouter } from '@tarojs/taro'
import { PHASE2_COACH_ENABLED_FLAG } from '@/constants/flags'
import { coachTaskService } from '@/services/coachTaskService'
import { useUserStore } from '@/store/userStore'
import {
  COACH_DRILL_CATEGORY_LABEL,
  filterDrillsByCategory,
  findDrillIndexInList,
  type CoachDrillCategory,
} from '@/utils/coachDrillFilter'
import './index.scss'

function currentWeekMondayIso(): string {
  const now = new Date()
  const day = now.getDay()
  const diff = day === 0 ? -6 : 1 - day
  const monday = new Date(now)
  monday.setDate(now.getDate() + diff)
  const y = monday.getFullYear()
  const m = String(monday.getMonth() + 1).padStart(2, '0')
  const d = String(monday.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

const CATEGORY_TABS: CoachDrillCategory[] = ['all', 'full_swing', 'putting', 'chipping']

const CoachTaskAssignPage: FC = () => {
  const router = useRouter()
  const studentUserId = (router.params.studentUserId || '').trim()
  const studentName = decodeURIComponent(router.params.studentName || '').trim()
  const presetDrillId = (router.params.drillId || '').trim()
  const presetIssue = decodeURIComponent(router.params.targetIssue || '').trim()
  const currentRole = useUserStore((s) => s.currentRole)

  const [category, setCategory] = useState<CoachDrillCategory>('all')
  const drillOptions = useMemo(() => filterDrillsByCategory(category), [category])
  const [drillIndex, setDrillIndex] = useState(0)
  const [targetCount, setTargetCount] = useState('3')
  const [coachNote, setCoachNote] = useState('')
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    setDrillIndex(findDrillIndexInList(drillOptions, presetDrillId))
  }, [drillOptions, presetDrillId])

  useEffect(() => {
    if (presetIssue && !coachNote) {
      setCoachNote(`针对 ${presetIssue} 加强练习`)
    }
  }, [presetIssue, coachNote])

  const handleSubmit = async () => {
    if (!studentUserId || submitting) return
    const count = Number.parseInt(targetCount, 10)
    if (!Number.isFinite(count) || count < 1 || count > 99) {
      Taro.showToast({ title: '次数请填 1-99', icon: 'none' })
      return
    }
    const drill = drillOptions[drillIndex]
    if (!drill) {
      Taro.showToast({ title: '请选择训练动作', icon: 'none' })
      return
    }
    setSubmitting(true)
    try {
      await coachTaskService.assign({
        student_user_id: studentUserId,
        source_type: 'drill',
        drill_id: drill.drill_id,
        target_week: currentWeekMondayIso(),
        target_count: count,
        target_issue: presetIssue || drill.target_issue,
        coach_note: coachNote.trim() || undefined,
      })
      Taro.showToast({ title: '已派发到训练 Tab', icon: 'success' })
      setTimeout(() => {
        Taro.navigateBack().catch(() => undefined)
      }, 600)
    } catch (e) {
      Taro.showToast({
        title: e instanceof Error ? e.message : '派发失败',
        icon: 'none',
      })
    } finally {
      setSubmitting(false)
    }
  }

  if (!PHASE2_COACH_ENABLED_FLAG || currentRole !== 'coach') {
    return (
      <View className='coach-task-assign coach-task-assign--empty'>
        <Text>请切换教练模式后再布置作业</Text>
      </View>
    )
  }

  if (!studentUserId) {
    return (
      <View className='coach-task-assign coach-task-assign--empty'>
        <Text>缺少学员 ID</Text>
      </View>
    )
  }

  const selectedDrill = drillOptions[drillIndex]

  return (
    <View className='coach-task-assign'>
      <Text className='coach-task-assign__title'>布置本周作业</Text>
      <Text className='coach-task-assign__meta'>
        学员：{studentName || studentUserId.slice(0, 8)}… · 派发后出现在学员「训练」Tab
      </Text>

      <Text className='coach-task-assign__label'>动作类目</Text>
      <View className='coach-task-assign__tabs'>
        {CATEGORY_TABS.map((tab) => (
          <Text
            key={tab}
            className={`coach-task-assign__tab${
              category === tab ? ' coach-task-assign__tab--active' : ''
            }`}
            onClick={() => {
              setCategory(tab)
              setDrillIndex(0)
            }}
          >
            {COACH_DRILL_CATEGORY_LABEL[tab]}
          </Text>
        ))}
      </View>

      <Text className='coach-task-assign__label'>训练动作</Text>
      <Picker
        mode='selector'
        range={drillOptions.map((d) => d.name)}
        value={drillIndex}
        onChange={(e) => setDrillIndex(Number(e.detail.value) || 0)}
      >
        <View className='coach-task-assign__picker'>
          <Text className='coach-task-assign__picker-text'>
            {selectedDrill?.name || '请选择'}
          </Text>
          {selectedDrill?.category ? (
            <Text className='coach-task-assign__picker-meta'>
              {COACH_DRILL_CATEGORY_LABEL[selectedDrill.category as CoachDrillCategory] ||
                selectedDrill.category}
            </Text>
          ) : null}
        </View>
      </Picker>

      <Text className='coach-task-assign__label'>目标次数</Text>
      <Input
        className='coach-task-assign__input'
        type='number'
        value={targetCount}
        onInput={(e) => setTargetCount(String(e.detail.value || ''))}
      />

      <Text className='coach-task-assign__label'>备注（可选）</Text>
      <Textarea
        className='coach-task-assign__textarea'
        value={coachNote}
        maxlength={500}
        placeholder='给学员一句练习提示'
        onInput={(e) => setCoachNote(String(e.detail.value || ''))}
      />

      <Button
        className='coach-task-assign__submit'
        loading={submitting}
        onClick={() => void handleSubmit()}
      >
        派发到学员训练 Tab
      </Button>
    </View>
  )
}

export default CoachTaskAssignPage
