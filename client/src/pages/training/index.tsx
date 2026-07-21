/**
 * W7-T3：训练计划页面.
 *
 * 数据流：
 *   页面进入 → `trainingService.getCurrentPlan()`
 *     - null → 空态（"先上传一次挥杆视频即可自动生成本周计划"）
 *     - 有 plan → 顶部进度条 + 按日期分组的任务卡片列表
 *   点任务 → 展开 drill 详情（复用 `constants/drillLibrary.ts`） → 「完成」按钮
 *   打卡成功 → toast + 局部刷新任务状态 + 更新 store 中 `user.current_streak_days`
 *   进步曲线（会员）：统计大卡 + 综合/六维折线图 + practice_logs 本月柱状图；非会员见锁定卡
 */

import { FC, useCallback, useEffect, useMemo, useState } from 'react'
import { Button, ScrollView, Text, View } from '@tarojs/components'
import Taro, { useDidShow } from '@tarojs/taro'
import { useShareAppMessage, useShareTimeline } from '@/adapters/share'
import EnvBadge from '@/components/EnvBadge'
import { APP_SHARE_MESSAGE, APP_SHARE_TIMELINE } from '@/constants/brandAssets'
import PracticeCalendar from '@/components/PracticeCalendar'
import '@/components/PracticeCalendar.scss'
import ProgressLineChart from '@/components/ProgressLineChart'
import '@/components/ProgressLineChart.scss'
import ScorePercentileCard, {
  type ScorePercentileData,
} from '@/components/ScorePercentileCard'
import '@/components/ScorePercentileCard.scss'
import TrustTierLegend from '@/components/TrustTierLegend'
import '@/components/TrustTierLegend.scss'
import VideoCard from '@/components/VideoCard'
import '@/components/VideoCard.scss'
import { trainingService } from '@/services/trainingService'
import { userService } from '@/services/userService'
import { describeIntermittentRequestFailure, isRequestError } from '@/services/request'
import { useUserStore } from '@/store/userStore'
import { useMembershipExpiringSoonModalOnShow } from '@/hooks/useMembershipExpiringSoonModalOnShow'
import { getDrillDetail } from '@/constants/drillLibrary'
import { getDrillVideoDetail } from '@/constants/drillVideoLibrary'
import { PHASE_COLOR, PHASE_LABEL, PHASE_ORDER, type SwingPhaseKey } from '@/constants/phaseLabels'
import { PAYMENT_ENABLED_FLAG, PHASE2_TRAINING_CATEGORIES_ENABLED_FLAG } from '@/constants/flags'
import type {
  PracticeLogItem,
  TrainingPlanDetail,
  TrainingTaskItem
} from '@/types/training'
import { switchToHome, toastTabNavigationFailure } from '@/utils/tabNav'
import {
  computeProgressStatCards,
  formatDelta,
  formatProgressNarrative,
  seriesForDimension,
  type ProgressDimension,
  type ProgressPoint,
} from '@/utils/progressCurveStats'
import {
  aggregatePracticeCounts,
  buildPracticeCalendarGrid,
  localDateKey,
  monthKeyNow,
  shiftMonthKey,
  type PracticeCalendarGrid,
} from '@/utils/practiceCalendarLayout'
import './index.scss'

const TrainingPage: FC = () => {
  const { user, token, initialized, bootstrap, fetchMe } = useUserStore()

  useShareAppMessage(() => ({ ...APP_SHARE_MESSAGE }))
  useShareTimeline(() => ({ ...APP_SHARE_TIMELINE }))

  useMembershipExpiringSoonModalOnShow(!!token)

  const [plan, setPlan] = useState<TrainingPlanDetail | null>(null)
  const [loading, setLoading] = useState(false)
  const [expandedTaskId, setExpandedTaskId] = useState<string | null>(null)
  const [submittingTaskId, setSubmittingTaskId] = useState<string | null>(null)
  const [progressPoints, setProgressPoints] = useState<ProgressPoint[]>([])
  /** P2-W16-B · ENG-05 · 同水平+同器材分位（cohort_size<5 时服务端把 percentile 设 null，前端自动隐藏整卡） */
  const [percentileData, setPercentileData] = useState<ScorePercentileData | null>(null)
  /** 进步曲线时间窗：0=不按天截断（服务端全量至 max_points）；90=近 90 天 */
  const [progressWindowDays, setProgressWindowDays] = useState<0 | 90>(90)
  /** 折线图维度：综合分或六维之一 */
  const [chartDimension, setChartDimension] = useState<ProgressDimension>('overall')
  /** 本月各日打卡次数（仅会员拉取 practice_logs；用于柱状趋势） */
  const [practiceDaily, setPracticeDaily] = useState<
    { day: number; count: number; dateKey: string }[]
  >([])
  const [practiceMonthTotal, setPracticeMonthTotal] = useState(0)
  const [practiceMonthKey, setPracticeMonthKey] = useState(() => monthKeyNow())
  const [practiceCalendar, setPracticeCalendar] = useState<PracticeCalendarGrid>(() =>
    buildPracticeCalendarGrid(monthKeyNow(), new Map()),
  )
  const [drillCategoryFilter, setDrillCategoryFilter] = useState<
    'all' | 'full_swing' | 'putting' | 'chipping'
  >('all')

  const matchesDrillCategory = useCallback(
    (task: TrainingTaskItem) => {
      if (!PHASE2_TRAINING_CATEGORIES_ENABLED_FLAG || drillCategoryFilter === 'all') {
        return true
      }
      const cat = getDrillDetail(task.drill_id).category || 'full_swing'
      return cat === drillCategoryFilter
    },
    [drillCategoryFilter],
  )

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

  /**
   * P2-W16-B · 拉同水平分位卡数据.
   *
   * club_type 选取策略：从 progressPoints 找最近一个 ProgressPoint，但 ProgressPoint
   * schema 暂未透传 club_type。MVP 期固定查 ``iron_7``（最常用 7 号铁）；W17+ 加切换器
   * 时再让父组件透传 clubType。
   *
   * cohort_size < 5 时服务端把 percentile 设 null，<ScorePercentileCard /> 整卡自动不渲染。
   */
  const loadPercentile = useCallback(async () => {
    if (!token) return
    if (!useUserStore.getState().user?.is_member) {
      setPercentileData(null)
      return
    }
    try {
      const res = await userService.getScorePercentile('iron_7')
      setPercentileData(res)
    } catch {
      setPercentileData(null)
    }
  }, [token])

  const loadPracticeCurve = useCallback(async () => {
    if (!token) return
    if (!useUserStore.getState().user?.is_member) {
      setPracticeDaily([])
      setPracticeMonthTotal(0)
      setPracticeCalendar(buildPracticeCalendarGrid(practiceMonthKey, new Map()))
      return
    }
    try {
      const logs = await trainingService.listPracticeLogs(practiceMonthKey)
      const counts = aggregatePracticeCounts(logs)
      const daily = buildDailyCounts(practiceMonthKey, logs)
      setPracticeDaily(daily)
      setPracticeMonthTotal(logs.length)
      setPracticeCalendar(
        buildPracticeCalendarGrid(practiceMonthKey, counts, localDateKey()),
      )
    } catch {
      setPracticeDaily([])
      setPracticeMonthTotal(0)
      setPracticeCalendar(buildPracticeCalendarGrid(practiceMonthKey, new Map()))
    }
  }, [token, practiceMonthKey])

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
        void loadPercentile()
      })
  })

  useEffect(() => {
    if (!token || !user?.is_member) return
    void loadProgress()
    void loadPercentile()
  }, [token, user?.is_member, progressWindowDays, loadProgress, loadPercentile])

  useEffect(() => {
    if (!token || !user?.is_member) return
    void loadPracticeCurve()
  }, [token, user?.is_member, practiceMonthKey, loadPracticeCurve])

  const { coachTasks, proTasks, standardTasks } = useMemo(() => {
    const all = plan?.tasks ?? []
    return {
      coachTasks: all.filter((t) => t.task_kind === 'coach_assigned'),
      proTasks: all.filter((t) => t.task_kind === 'pro_clip_try_it'),
      standardTasks: all.filter(
        (t) =>
          t.task_kind !== 'pro_clip_try_it' &&
          t.task_kind !== 'coach_assigned' &&
          matchesDrillCategory(t),
      ),
    }
  }, [plan, matchesDrillCategory])

  const groupedCoach = useMemo(() => groupByDate(coachTasks), [coachTasks])

  const groupedPro = useMemo(() => groupByDate(proTasks), [proTasks])
  const grouped = useMemo(() => groupByDate(standardTasks), [standardTasks])
  const progressPercent = useMemo(() => {
    if (!plan || plan.total_tasks === 0) return 0
    return Math.round((plan.completed_tasks / plan.total_tasks) * 100)
  }, [plan])

  const practiceMaxCount = useMemo(
    () => Math.max(1, ...practiceDaily.map((d) => d.count)),
    [practiceDaily]
  )

  const progressStats = useMemo(
    () => computeProgressStatCards(progressPoints, user?.stats),
    [progressPoints, user?.stats],
  )

  const chartSeries = useMemo(
    () =>
      seriesForDimension(progressPoints, chartDimension).map((p) => ({
        value: p.value,
        label: p.label,
        // P2-W12-1：V2 报告才有 tier；V1 报告 tier=undefined → 走默认主色
        tier: p.tier,
      })),
    [progressPoints, chartDimension],
  )

  const chartAccent =
    chartDimension === 'overall'
      ? undefined
      : PHASE_COLOR[chartDimension as SwingPhaseKey]

  const dimensionOptions: { key: ProgressDimension; label: string }[] = useMemo(
    () => [
      { key: 'overall', label: '综合' },
      ...PHASE_ORDER.map((k) => ({ key: k as ProgressDimension, label: PHASE_LABEL[k] })),
    ],
    [],
  )

  const statCardsInner =
    progressPoints.length > 0 ? (
      <View className='training__stat-grid'>
        <View className='training__stat-card'>
          <Text className='training__stat-value'>{progressStats.totalAnalyses}</Text>
          <Text className='training__stat-label'>累计分析</Text>
        </View>
        <View className='training__stat-card'>
          <Text className='training__stat-value'>{progressStats.totalPractices}</Text>
          <Text className='training__stat-label'>累计练习</Text>
        </View>
        <View className='training__stat-card'>
          <Text className='training__stat-value'>{progressStats.streakDays}</Text>
          <Text className='training__stat-label'>连续打卡</Text>
        </View>
        <View className='training__stat-card'>
          <Text className='training__stat-value training__stat-value--delta'>
            {progressStats.bestImprovement
              ? `${progressStats.bestImprovement.label} ${formatDelta(progressStats.bestImprovement.delta)}`
              : formatDelta(progressStats.windowScoreDelta)}
          </Text>
          <Text className='training__stat-label'>
            {progressStats.bestImprovement ? '最大改善维度' : '窗口内得分变化'}
          </Text>
        </View>
      </View>
    ) : null

  const progressNarrative = useMemo(
    () => formatProgressNarrative(progressStats, progressPoints),
    [progressStats, progressPoints],
  )

  const canGoNextPracticeMonth = practiceMonthKey < monthKeyNow()

  const practiceCalendarInner = user?.is_member ? (
    <View className='training__calendar-wrap'>
      <Text className='training__trend-title'>打卡月历</Text>
      <PracticeCalendar
        embedded
        grid={practiceCalendar}
        canGoNext={canGoNextPracticeMonth}
        onPrevMonth={() => setPracticeMonthKey((k) => shiftMonthKey(k, -1))}
        onNextMonth={() => {
          if (!canGoNextPracticeMonth) return
          setPracticeMonthKey((k) => shiftMonthKey(k, 1))
        }}
      />
    </View>
  ) : null

  const scoreTrendInner =
    progressPoints.length > 0 ? (
      <>
        {statCardsInner}
        <Text className='training__trend-title'>得分走势</Text>
        <Text className='training__trend-hint'>
          {chartDimension === 'overall'
            ? '综合分随时间变化（0–100）'
            : `${PHASE_LABEL[chartDimension as SwingPhaseKey]}维度变化`}
        </Text>
        <ScrollView scrollX className='training__dim-scroll' showScrollbar={false} enableFlex>
          <View className='training__dim-row'>
            {dimensionOptions.map((opt) => (
              <Text
                key={opt.key}
                className={`training__dim-pill ${chartDimension === opt.key ? 'is-active' : ''}`}
                onClick={() => setChartDimension(opt.key)}
              >
                {opt.label}
              </Text>
            ))}
          </View>
        </ScrollView>
        <ProgressLineChart
          points={chartSeries}
          accentColor={chartAccent}
          canvasId='training-progress-line'
        />
        {/* P2-W13-A：仅当当前曲线包含 V2 报告点（tier 存在）才显示图例；
            全 V1 报告时不显示，避免给老用户看到无用色块 */}
        <TrustTierLegend hasV2Points={chartSeries.some((p) => p.tier)} />
        {/* P2-W16-B：同水平+同器材分位卡（cohort_size<5 时服务端 percentile=null，整卡不渲染） */}
        <ScorePercentileCard data={percentileData} />
        {progressNarrative ? (
          <Text className='training__progress-narrative'>{progressNarrative}</Text>
        ) : null}
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
      {scoreTrendInner || practiceCalendarInner || practiceBarsInner ? (
        <>
          {scoreTrendInner ? (
            <View className='training__trend training__trend--in-curve'>
              {scoreTrendInner}
            </View>
          ) : null}
          {practiceCalendarInner ? (
            <View className='training__trend training__trend--in-curve training__trend--calendar'>
              {practiceCalendarInner}
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
      // PP-09：练完再拍——同机位再拍一次看进步
      const modal = await Taro.showModal({
        title: `打卡成功！连续 ${res.current_streak_days} 天`,
        content: '建议用相同机位再拍一次挥杆，对比是否改善。',
        confirmText: '去拍摄',
        cancelText: '稍后再说',
      })
      if (modal.confirm) {
        Taro.navigateTo({ url: '/pages/analysis/capture' }).catch(() => undefined)
      }
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

  const renderTaskCard = (task: TrainingTaskItem) => {
    const drill = getDrillDetail(task.drill_id)
    const drillVideo = getDrillVideoDetail(task.drill_id)
    const isExpanded = expandedTaskId === task.id
    const isDone = task.status === 'completed'
    const isProTryIt = task.task_kind === 'pro_clip_try_it'
    const isCoachAssigned = task.task_kind === 'coach_assigned'
    const displayName =
      isProTryIt && task.pro_player_name
        ? `对照 ${task.pro_player_name} 的挥杆`
        : drill.name
    return (
      <View
        key={task.id}
        className={`training__task ${isDone ? 'is-done' : ''} ${
          isProTryIt ? 'training__task--pro' : ''
        } ${isCoachAssigned ? 'training__task--coach' : ''}`}
      >
        <View
          className='training__task-head'
          onClick={() => setExpandedTaskId(isExpanded ? null : task.id)}
        >
          <View className='training__task-head-main'>
            <Text className='training__task-name'>
              {isDone ? '✅ ' : ''}
              {displayName}
            </Text>
            <Text className='training__task-meta'>
              {isCoachAssigned && task.coach_display_name
                ? `${task.coach_display_name} 布置 · `
                : ''}
              {isCoachAssigned && task.coach_target_count
                ? `目标 ${task.coach_target_count} 次 · `
                : ''}
              {isProTryIt ? '对照球手 · ' : ''}
              {drill.duration_minutes} 分钟 · {drill.difficulty} · {drill.sets} 组
            </Text>
            {isCoachAssigned && task.coach_note ? (
              <Text className='training__task-coach-note'>{task.coach_note}</Text>
            ) : null}
            {isProTryIt && task.pro_clip_unavailable && (
              <Text className='training__task-warn'>参考镜头已下架，任务仍可完成</Text>
            )}
          </View>
          <Text className='training__task-arrow'>{isExpanded ? '收起' : '展开'}</Text>
        </View>

        {isExpanded && (
          <View className='training__task-body'>
            {isProTryIt && (
              <Text className='training__task-pro-hint'>
                参考职业镜头，用相同杆型与机位拍摄一条自己的挥杆，完成后打卡。
              </Text>
            )}
            {drillVideo && (
              <View className='training__task-video'>
                <VideoCard
                  attachment={{
                    type: 'video_card',
                    drill_id: task.drill_id,
                    title: drillVideo.title,
                  }}
                />
              </View>
            )}
            <Text className='training__task-desc'>{drill.description}</Text>
            <View className='training__steps'>
              {drill.steps.map((step, idx) => (
                <View key={idx} className='training__step'>
                  <Text className='training__step-index'>{idx + 1}</Text>
                  <Text className='training__step-text'>{step}</Text>
                </View>
              ))}
            </View>
            {drill.tips && drill.tips.length > 0 ? (
              <View className='training__tips'>
                <Text className='training__tips-title'>教练提示</Text>
                {drill.tips.map((tip, idx) => (
                  <View key={idx} className='training__tip'>
                    <Text className='training__tip-bullet'>·</Text>
                    <Text className='training__tip-text'>{tip}</Text>
                  </View>
                ))}
              </View>
            ) : null}
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
    // 无训练计划时空态只留「还没有训练计划 + 去上传视频」CTA；不再在顶部叠加
    // 进步曲线/打卡月历（会员）或「了解会员」卡（非会员）——那会喧宾夺主，且卡片
    // 自身 margin 与空态容器 padding 叠加会左右不对称（看着偏）。进步曲线在有计划页展示。
    return (
      <View className='training training--empty'>
        <EnvBadge />
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
    <View className='training'>
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

      {PHASE2_TRAINING_CATEGORIES_ENABLED_FLAG && (
        <View className='training__category-filter'>
          {(
            [
              ['all', '全部'],
              ['full_swing', '全挥杆'],
              ['putting', '推杆'],
              ['chipping', '切杆'],
            ] as const
          ).map(([key, label]) => (
            <View
              key={key}
              className={[
                'training__category-chip',
                drillCategoryFilter === key ? 'training__category-chip--active' : '',
              ]
                .filter(Boolean)
                .join(' ')}
              onClick={() => setDrillCategoryFilter(key)}
            >
              <Text>{label}</Text>
            </View>
          ))}
        </View>
      )}

      {groupedCoach.length > 0 && (
        <View className='training__coach-section'>
          <Text className='training__coach-section-title'>教练布置的任务</Text>
          {groupedCoach.map(({ date, tasks }) => (
            <View key={`coach-${date}`} className='training__day'>
              <View className='training__day-header'>
                <Text className='training__day-label'>{formatDayLabel(date)}</Text>
                <Text className='training__day-count'>{tasks.length} 个任务</Text>
              </View>
              {tasks.map((task) => renderTaskCard(task))}
            </View>
          ))}
        </View>
      )}

      {groupedPro.length > 0 && (
        <View className='training__pro-section'>
          <Text className='training__pro-section-title'>对照球手训练</Text>
          {groupedPro.map(({ date, tasks }) => (
            <View key={`pro-${date}`} className='training__day'>
              <View className='training__day-header'>
                <Text className='training__day-label'>{formatDayLabel(date)}</Text>
                <Text className='training__day-count'>{tasks.length} 个任务</Text>
              </View>
              {tasks.map((task) => renderTaskCard(task))}
            </View>
          ))}
        </View>
      )}

      {grouped.length > 0 && (groupedCoach.length > 0 || groupedPro.length > 0) && (
        <Text className='training__section-divider'>分析驱动训练</Text>
      )}

      {grouped.map(({ date, tasks }) => (
        <View key={date} className='training__day'>
          <View className='training__day-header'>
            <Text className='training__day-label'>{formatDayLabel(date)}</Text>
            <Text className='training__day-count'>{tasks.length} 个任务</Text>
          </View>
          {tasks.map((task) => renderTaskCard(task))}
        </View>
      ))}
    </View>
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
