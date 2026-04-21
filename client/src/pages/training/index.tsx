/**
 * W7-T3：训练计划页面.
 *
 * 数据流：
 *   页面进入 → `trainingService.getCurrentPlan()`
 *     - null → 空态（"先上传一次挥杆视频即可自动生成本周计划"）
 *     - 有 plan → 顶部进度条 + 按日期分组的任务卡片列表
 *   点任务 → 展开 drill 详情（复用 `constants/drillLibrary.ts`） → 「完成」按钮
 *   打卡成功 → toast + 局部刷新任务状态 + 更新 store 中 `user.current_streak_days`
 */

import { FC, useCallback, useEffect, useMemo, useState } from 'react'
import { Button, ScrollView, Text, View } from '@tarojs/components'
import Taro, { useDidShow } from '@tarojs/taro'
import { trainingService } from '@/services/trainingService'
import { useUserStore } from '@/store/userStore'
import { getDrillDetail } from '@/constants/drillLibrary'
import type { TrainingPlanDetail, TrainingTaskItem } from '@/types/training'
import './index.scss'

const TrainingPage: FC = () => {
  const { user, fetchMe } = useUserStore()
  const [plan, setPlan] = useState<TrainingPlanDetail | null>(null)
  const [loading, setLoading] = useState(false)
  const [expandedTaskId, setExpandedTaskId] = useState<string | null>(null)
  const [submittingTaskId, setSubmittingTaskId] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await trainingService.getCurrentPlan()
      setPlan(res)
    } catch (e) {
      Taro.showToast({ title: '加载失败，请稍后再试', icon: 'none' })
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  useDidShow(() => {
    // 分析完成后回到这页时，拉最新 plan + streak
    load()
    fetchMe().catch(() => undefined)
  })

  const grouped = useMemo(() => groupByDate(plan?.tasks ?? []), [plan])
  const progressPercent = useMemo(() => {
    if (!plan || plan.total_tasks === 0) return 0
    return Math.round((plan.completed_tasks / plan.total_tasks) * 100)
  }, [plan])

  async function handleComplete(taskId: string) {
    if (submittingTaskId) return
    setSubmittingTaskId(taskId)
    try {
      const res = await trainingService.completeTask(taskId, {})
      Taro.showToast({
        title: `打卡成功！连续 ${res.current_streak_days} 天`,
        icon: 'success'
      })
      // 局部更新 plan
      setPlan((prev) =>
        prev
          ? {
              ...prev,
              completed_tasks: res.plan_completed_tasks,
              tasks: prev.tasks.map((t) =>
                t.id === taskId ? { ...t, ...res.task } : t
              )
            }
          : prev
      )
      setExpandedTaskId(null)
      // 刷新 user 拿最新 streak
      fetchMe().catch(() => undefined)
    } catch (e: any) {
      const msg = e?.data?.message || e?.message || '打卡失败'
      Taro.showToast({ title: msg, icon: 'none' })
    } finally {
      setSubmittingTaskId(null)
    }
  }

  if (loading && !plan) {
    return (
      <View className='training training--empty'>
        <Text className='training__empty-icon'>⏳</Text>
        <Text>加载中...</Text>
      </View>
    )
  }

  if (!plan) {
    return (
      <View className='training training--empty'>
        <Text className='training__empty-icon'>🏋️</Text>
        <Text className='training__empty-title'>还没有训练计划</Text>
        <Text className='training__empty-sub'>
          先上传一次挥杆视频，AI 会根据分析结果为你生成本周专属训练
        </Text>
        <Button
          className='training__empty-cta'
          type='primary'
          onClick={() => Taro.switchTab({ url: '/pages/index/index' })}
        >
          去上传视频
        </Button>
      </View>
    )
  }

  return (
    <ScrollView scrollY className='training'>
      <View className='training__hero'>
        <Text className='training__hero-title'>本周训练</Text>
        <Text className='training__hero-sub'>
          {formatWeekRange(plan.week_start, plan.week_end)}
        </Text>
        <View className='training__progress'>
          <View className='training__progress-track'>
            <View
              className='training__progress-bar'
              style={{ width: `${progressPercent}%` }}
            />
          </View>
          <Text className='training__progress-label'>
            {plan.completed_tasks} / {plan.total_tasks} 已完成
          </Text>
        </View>
        {user && (
          <View className='training__streak'>
            <Text className='training__streak-icon'>🔥</Text>
            <Text className='training__streak-text'>
              连续训练 {user.stats?.streak_days ?? 0} 天
            </Text>
          </View>
        )}
      </View>

      {plan.ai_summary && (
        <View className='training__summary'>
          <Text className='training__summary-title'>教练本周提示</Text>
          <Text className='training__summary-body'>{plan.ai_summary}</Text>
        </View>
      )}

      {grouped.map(({ date, tasks }) => (
        <View key={date} className='training__day'>
          <View className='training__day-header'>
            <Text className='training__day-label'>{formatDayLabel(date)}</Text>
            <Text className='training__day-count'>{tasks.length} 个任务</Text>
          </View>
          {tasks.map((task) => {
            const drill = getDrillDetail(task.drill_id)
            const isExpanded = expandedTaskId === task.id
            const isDone = task.status === 'completed'
            return (
              <View
                key={task.id}
                className={`training__task ${isDone ? 'is-done' : ''}`}
              >
                <View
                  className='training__task-head'
                  onClick={() =>
                    setExpandedTaskId(isExpanded ? null : task.id)
                  }
                >
                  <View className='training__task-head-main'>
                    <Text className='training__task-name'>
                      {isDone ? '✅ ' : ''}
                      {drill.name}
                    </Text>
                    <Text className='training__task-meta'>
                      {drill.duration_minutes} 分钟 · {drill.difficulty} ·{' '}
                      {drill.sets} 组
                    </Text>
                  </View>
                  <Text className='training__task-arrow'>
                    {isExpanded ? '收起' : '展开'}
                  </Text>
                </View>

                {isExpanded && (
                  <View className='training__task-body'>
                    <Text className='training__task-desc'>
                      {drill.description}
                    </Text>
                    <View className='training__steps'>
                      {drill.steps.map((step, idx) => (
                        <View key={idx} className='training__step'>
                          <Text className='training__step-index'>{idx + 1}</Text>
                          <Text className='training__step-text'>{step}</Text>
                        </View>
                      ))}
                    </View>
                    {!isDone ? (
                      <Button
                        className='training__task-cta'
                        type='primary'
                        loading={submittingTaskId === task.id}
                        onClick={() => handleComplete(task.id)}
                      >
                        {submittingTaskId === task.id ? '提交中...' : '完成打卡'}
                      </Button>
                    ) : (
                      <Text className='training__task-completed-label'>
                        已于{' '}
                        {task.completed_at
                          ? new Date(task.completed_at).toLocaleDateString()
                          : ''}{' '}
                        完成
                      </Text>
                    )}
                  </View>
                )}
              </View>
            )
          })}
        </View>
      ))}
    </ScrollView>
  )
}

export default TrainingPage

// ========== 辅助 ==========
function groupByDate(tasks: TrainingTaskItem[]) {
  const map = new Map<string, TrainingTaskItem[]>()
  for (const t of tasks) {
    const arr = map.get(t.scheduled_date) ?? []
    arr.push(t)
    map.set(t.scheduled_date, arr)
  }
  const sorted = [...map.entries()].sort(([a], [b]) => (a < b ? -1 : 1))
  return sorted.map(([date, list]) => ({
    date,
    tasks: list.sort((a, b) => a.sort_order - b.sort_order)
  }))
}

function formatWeekRange(start: string, end: string) {
  // "2026-04-20" → "4.20"
  const [, sm, sd] = start.split('-')
  const [, em, ed] = end.split('-')
  return `${Number(sm)}.${Number(sd)} - ${Number(em)}.${Number(ed)}`
}

function formatDayLabel(d: string) {
  const today = new Date()
  const todayStr = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`
  if (d === todayStr) return '今天'
  const [, m, day] = d.split('-')
  const dateObj = new Date(d + 'T00:00:00')
  const wk = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'][
    dateObj.getDay()
  ]
  return `${Number(m)}月${Number(day)}日 ${wk}`
}
