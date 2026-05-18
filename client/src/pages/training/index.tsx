/**
 * W7-T3：训练计划页面.
 *
 * 数据流：
 *   页面进入 → `trainingService.getCurrentPlan()`
 *     - null → 空态（"先上传一次挥杆视频即可自动生成本周计划"）
 *     - 有 plan → 顶部进度条 + 按日期分组的任务卡片列表
 *   点任务 → 展开 drill 详情（复用 `constants/drillLibrary.ts`） → 「完成」按钮
 *   打卡成功 → toast + 局部刷新任务状态 + 更新 store 中 `user.current_streak_days`
 *   进步曲线（会员）：`analysis-progress` 综合分横滑 + `practice-logs?month=` 本月打卡柱状图；非会员见锁定卡
 */

import { FC, useCallback, useEffect, useMemo, useState } from 'react'
import { Button, ScrollView, Text, View } from '@tarojs/components'
import Taro, { useDidShow } from '@tarojs/taro'
import EnvBadge from '@/components/EnvBadge'
import { trainingService } from '@/services/trainingService'
import { userService } from '@/services/userService'
import { describeIntermittentRequestFailure, isRequestError } from '@/services/request'
import { useUserStore } from '@/store/userStore'
import { getDrillDetail } from '@/constants/drillLibrary'
import { PAYMENT_ENABLED_FLAG } from '@/constants/flags'
import type {
  PracticeLogItem,
  TrainingPlanDetail,
  TrainingTaskItem
} from '@/types/training'
import { switchToHome, toastTabNavigationFailure } from '@/utils/tabNav'
import './index.scss'

const TrainingPage: FC = () => {
  const { user, token, initialized, bootstrap, fetchMe } = useUserStore()
  const [plan, setPlan] = useState<TrainingPlanDetail | null>(null)
  const [loading, setLoading] = useState(false)
  const [expandedTaskId, setExpandedTaskId] = useState<string | null>(null)
  const [submittingTaskId, setSubmittingTaskId] = useState<string | null>(null)
  const [progressPoints, setProgressPoints] = useState<
    { analysis_id: string; analyzed_at: string; overall_score: number }[]
  >([])
  /** 进步曲线时间窗：0=不按天截断（服务端全量至 max_points）；90=近 90 天 */
  const [progressWindowDays, setProgressWindowDays] = useState<0 | 90>(90)
  /** 本月各日打卡次数（仅会员拉取 practice_logs；用于柱状趋势） */
  const [practiceDaily, setPracticeDaily] = useState<
    { day: number; count: number; dateKey: string }[]
  >([])
  const [practiceMonthTotal, setPracticeMonthTotal] = useState(0)

  const load = useCallback(async () => {
    if (!token) return
    setLoading(true)
    try {
      const res = await trainingService.getCurrentPlan()
      setPlan(res)
    } catch (e) {
      let base = '加载失败，请稍后再试'
      if (isRequestError(e)) {
        base =
          e.kind === 'business'
            ? e.message?.trim() || base
            : describeIntermittentRequestFailure(e).toastTitle
      }
      const rid =
        isRequestError(e) &&
        typeof e.requestId === 'string' &&
        e.requestId.trim()
          ? e.requestId.trim()
          : ''
      const line =
        rid && `${base}\n追踪ID ${rid}`.length <= 220
          ? `${base}\n追踪ID ${rid}`
          : rid
            ? `${base.slice(0, 170)} …${rid.slice(-12)}`
            : base
      Taro.showToast({ title: line.slice(0, 220), icon: 'none', duration: rid ? 4500 : 2500 })
    } finally {
      setLoading(false)
    }
  }, [token])

  const loadProgress = useCallback(async () => {
    if (!token) return
    if (!useUserStore.getState().user?.is_member) {
      setProgressPoints([])
      return
    }
    try {
      const res = await userService.getAnalysisProgress(
        progressWindowDays > 0 ? progressWindowDays : undefined,
      )
      setProgressPoints(res.points ?? [])
    } catch {
      setProgressPoints([])
    }
  }, [token, progressWindowDays])

  const loadPracticeCurve = useCallback(async () => {
    if (!token) return
    if (!useUserStore.getState().user?.is_member) {
      setPracticeDaily([])
      setPracticeMonthTotal(0)
      return
    }
    const monthKey = monthKeyNow()
    try {
      const logs = await trainingService.listPracticeLogs(monthKey)
      const daily = buildDailyCounts(monthKey, logs)
      setPracticeDaily(daily)
      setPracticeMonthTotal(logs.length)
    } catch {
      setPracticeDaily([])
      setPracticeMonthTotal(0)
    }
  }, [token])

  useEffect(() => {
    if (!initialized) {
      void bootstrap()
    }
  }, [initialized, bootstrap])

  useEffect(() => {
    if (token) {
      void load()
    } else {
      setPlan(null)
      setLoading(false)
      setProgressPoints([])
      setPracticeDaily([])
      setPracticeMonthTotal(0)
    }
  }, [token, load])

  useDidShow(() => {
    if (!token) return
    load()
    void fetchMe()
      .catch(() => undefined)
      .finally(() => {
        void loadProgress()
        void loadPracticeCurve()
      })
  })

  useEffect(() => {
    if (!token || !user?.is_member) return
    void loadProgress()
  }, [token, user?.is_member, progressWindowDays, loadProgress])

  const grouped = useMemo(() => groupByDate(plan?.tasks ?? []), [plan])
  const progressPercent = useMemo(() => {
    if (!plan || plan.total_tasks === 0) return 0
    return Math.round((plan.completed_tasks / plan.total_tasks) * 100)
  }, [plan])

  const shortAt = (iso: string) => {
    const d = new Date(iso)
    if (Number.isNaN(d.getTime())) return iso.slice(0, 10)
    return `${d.getMonth() + 1}/${d.getDate()}`
  }

  const practiceMaxCount = useMemo(
    () => Math.max(1, ...practiceDaily.map((d) => d.count)),
    [practiceDaily]
  )

  const scoreTrendInner =
    progressPoints.length > 0 ? (
      <>
        <Text className='training__trend-title'>综合得分走势</Text>
        <Text className='training__trend-hint'>历次分析综合分（按时间从早到晚）</Text>
        <ScrollView
          scrollX
          className='training__trend-scroll'
          showScrollbar={false}
          enableFlex
        >
          <View className='training__trend-row'>
            {progressPoints.map((p) => (
              <View key={p.analysis_id} className='training__trend-chip'>
                <Text className='training__trend-score'>{p.overall_score}</Text>
                <Text className='training__trend-date'>{shortAt(p.analyzed_at)}</Text>
              </View>
            ))}
          </View>
        </ScrollView>
      </>
    ) : null

  const practiceBarsInner =
    practiceMonthTotal > 0 ? (
      <>
        <Text className='training__trend-title training__practice-title'>
          本月训练打卡
        </Text>
        <Text className='training__trend-hint'>
          基于计划任务的打卡记录，共 {practiceMonthTotal} 次
        </Text>
        <ScrollView
          scrollX
          className='training__trend-scroll'
          showScrollbar={false}
          enableFlex
        >
          <View className='training__practice-bars-row'>
            {practiceDaily.map(({ day, count, dateKey }) => (
              <View key={dateKey} className='training__practice-bar-col'>
                <View className='training__practice-bar-track'>
                  <View
                    className='training__practice-bar-fill'
                    style={{
                      height:
                        count === 0
                          ? '6rpx'
                          : `${Math.max(14, Math.round((count / practiceMaxCount) * 100))}%`
                    }}
                  />
                </View>
                <Text className='training__practice-bar-day'>{day}</Text>
              </View>
            ))}
          </View>
        </ScrollView>
      </>
    ) : null

  const memberProgressSection = !user?.is_member ? (
    <View className='training__curve-lock'>
      <Text className='training__curve-lock-title'>进步曲线</Text>
      <Text className='training__curve-lock-desc'>
        {PAYMENT_ENABLED_FLAG
          ? '进步曲线为会员专属：可查看综合得分变化与本月的每日训练打卡分布。'
          : '当前为产品内测阶段，完整进步曲线随正式上线与会员权益一并开放；你仍可按免费配额完成分析与本周训练计划。'}
      </Text>
      {PAYMENT_ENABLED_FLAG ? (
        <Button
          className='training__curve-lock-cta'
          onClick={() =>
            Taro.navigateTo({ url: '/pages/profile/membership' })
          }
        >
          了解会员
        </Button>
      ) : null}
    </View>
  ) : (
    <View className='training__member-curve'>
      <Text className='training__member-curve-heading'>进步曲线</Text>
      <View className='training__window-pills'>
        <Text
          className={`training__pill ${progressWindowDays === 90 ? 'is-active' : ''}`}
          onClick={() => setProgressWindowDays(90)}
        >
          近 90 天
        </Text>
        <Text
          className={`training__pill ${progressWindowDays === 0 ? 'is-active' : ''}`}
          onClick={() => setProgressWindowDays(0)}
        >
          全部
        </Text>
      </View>
      {scoreTrendInner || practiceBarsInner ? (
        <>
          {scoreTrendInner ? (
            <View className='training__trend training__trend--in-curve'>
              {scoreTrendInner}
            </View>
          ) : null}
          {practiceBarsInner ? (
            <View className='training__trend training__trend--in-curve training__trend--practice'>
              {practiceBarsInner}
            </View>
          ) : null}
        </>
      ) : (
        <Text className='training__member-curve-empty'>
          完成挥杆分析与训练打卡后，将在此展示得分与本月打卡分布。
        </Text>
      )}
    </View>
  )

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
      void fetchMe()
        .catch(() => undefined)
        .finally(() => {
          void loadPracticeCurve()
        })
    } catch (e: unknown) {
      let title =
        isRequestError(e) && e.kind === 'business' && e.message?.trim()
          ? e.message.trim().slice(0, 220)
          : describeIntermittentRequestFailure(e).toastTitle
      Taro.showToast({ title, icon: 'none' })
    } finally {
      setSubmittingTaskId(null)
    }
  }

  if (!initialized) {
    return (
      <View className='training training--empty'>
        <Text className='training__empty-icon'>⏳</Text>
        <Text>加载中...</Text>
      </View>
    )
  }

  if (!token) {
    const goLogin = () => Taro.navigateTo({ url: '/pages/login/index' })
    return (
      <View className='training training--empty training--guest'>
        <EnvBadge />
        <Text className='training__empty-icon'>🏋️</Text>
        <Text className='training__empty-title'>训练计划</Text>
        <Text className='training__empty-sub'>
          登录并完成挥杆分析后，系统会根据报告为你生成本周训练任务与打卡提醒。
        </Text>
        <Button className='training__empty-cta' type='primary' onClick={goLogin}>
          登录后查看训练计划
        </Button>
      </View>
    )
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
        <EnvBadge />
        {memberProgressSection}
        <Text className='training__empty-icon'>🏋️</Text>
        <Text className='training__empty-title'>还没有训练计划</Text>
        <Text className='training__empty-sub'>
          先上传一次挥杆视频，AI 会根据分析结果为你生成本周专属训练
        </Text>
        <Button
          className='training__empty-cta'
          type='primary'
          onClick={() => void switchToHome().catch(toastTabNavigationFailure)}
        >
          去上传视频
        </Button>
      </View>
    )
  }

  return (
    <ScrollView scrollY className='training'>
      <View className='training__scroll-inner'>
      <EnvBadge />
      {memberProgressSection}
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
      </View>
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

/** 当前本地年月 `YYYY-MM`（与 `/users/me/practice-logs?month=` 一致） */
function monthKeyNow(): string {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
}

/** 将 practice_logs 聚合成「当月每日次数」，含打卡为 0 的日期（柱状图横轴） */
function buildDailyCounts(
  monthKey: string,
  logs: PracticeLogItem[]
): { day: number; count: number; dateKey: string }[] {
  const parts = monthKey.split('-')
  const y = Number(parts[0])
  const m = Number(parts[1])
  if (!y || !m) return []
  const lastDay = new Date(y, m, 0).getDate()
  const counts = new Map<string, number>()
  for (const log of logs) {
    const key = (log.practice_date ?? '').slice(0, 10)
    if (!key) continue
    counts.set(key, (counts.get(key) ?? 0) + 1)
  }
  const mm = String(m).padStart(2, '0')
  const out: { day: number; count: number; dateKey: string }[] = []
  for (let day = 1; day <= lastDay; day++) {
    const dd = String(day).padStart(2, '0')
    const dateKey = `${y}-${mm}-${dd}`
    out.push({ day, count: counts.get(dateKey) ?? 0, dateKey })
  }
  return out
}
