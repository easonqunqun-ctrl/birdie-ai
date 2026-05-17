/**
 * 分析等待页（MVP §4.2）
 *
 * 完整职责：
 *   1. 轮询 /analyses/{id}/status：`pending` 稍慢、`processing` 更频（useDidShow 恢复 /
 *      useDidHide 暂停），完成后约 250ms 跳转报告
 *   2. 基于后端 `stage` 字段映射到 5 阶段流转
 *      （W6-T4：去掉了"processing 持续时间本地模拟"，因为 backend 自己有
 *      stage 推进 task，会按真实预算推进 stage 字段；前端只读不算）
 *   3. 剩余秒数：优先采用后端 `estimated_remaining_seconds`，本地每秒 -1 平滑显示
 *   4. "你知道吗" 小贴士：从 `constants/swingTips.ts` 随机起点 + 8s 滚动
 *   5. status=completed → reLaunch 到 report 页
 *   6. status=failed → 错误 UI，两个按钮（重新拍摄 / 回首页）；若 quota_refunded 加文案
 *   7. ≥60s 非阻断文案「可能比预期稍久」；≥120s 仍终态占位「分析时间较长…」（通知 W8）
 *   8. 连续 3 次轮询失败 → 停止轮询 + toast
 *
 * 设计选型记录：
 *   - 阶段定义固化在本页 `STAGES`，后端 stage 字段的枚举值用来做"后端已经到该阶段"的
 *     语义映射（stage → 阶段索引）；前端不再做时间推进上限，避免与后端 stage 抢话语权
 *   - 轮询用裸 setTimeout 递归，不用 setInterval —— 更容易按 useDidShow/Hide 精准控制，
 *     并按 pending / processing 调整间隔
 */

import { FC, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { View, Text, Button } from '@tarojs/components'
import Taro, { useDidHide, useDidShow, useRouter } from '@tarojs/taro'
import { analysisService } from '@/services/analysisService'
import { describeIntermittentRequestFailure, isRequestError } from '@/services/request'
import { useAnalysisStore } from '@/store/analysisStore'
import { SUBSCRIBE_TPL_ANALYSIS_DONE } from '@/constants/subscribeTemplates'
import { SWING_TIPS, pickStartIndex } from '@/constants/swingTips'
import type {
  AnalysisStage,
  AnalysisStatusResponse,
} from '@/types/analysis'
import './waiting.scss'

/** 用户可见的阶段序列（UI 上展示） */
const STAGES: { key: string; label: string; backendStages: AnalysisStage[] }[] = [
  { key: 'received', label: '视频已接收', backendStages: ['preprocessing'] },
  { key: 'pose', label: '识别人体姿态', backendStages: ['pose_estimating'] },
  { key: 'swing', label: '分析挥杆动作', backendStages: ['phase_segmenting', 'scoring'] },
  { key: 'diagnose', label: '生成诊断建议', backendStages: ['diagnosing', 'generating'] },
  { key: 'render', label: '渲染分析报告', backendStages: [] },
]

/** 轮询间隔：排队中稍疏；分析中加密，更快感知完成 */
function pollDelayMs(status: AnalysisStatusResponse['status'] | null): number {
  if (status === 'pending') return 2200
  if (status === 'processing') return 1300
  return 1500
}

/** 完成后短暂留白再跳转（避免最后一帧 stage 看不见） */
const COMPLETE_REDIRECT_MS = 250
/** MVP：60s 非阻断提示「可能稍久」；120s 仍作为强提示/占位阈值 */
const SOFT_LONG_WAIT_SEC = 60
const TIMEOUT_FALLBACK_MS = 120_000
const TIPS_ROTATE_MS = 8000
const MAX_CONSECUTIVE_ERRORS = 3

/** W6-T4：把后端 stage 字段映射到 STAGES 数组下标（找不到时返回 0）。
 *  与之前的 `backendStageToMinIndex` 区别：不再叠加"本地时间推进"上限，
 *  完全以 backend 为准。后端 stage_progress 推进顺序和这里 STAGES 顺序一致。 */
function backendStageToIndex(stage: AnalysisStage | null | undefined): number {
  if (!stage) return 0
  const idx = STAGES.findIndex((s) => s.backendStages.includes(stage))
  return idx === -1 ? 0 : idx
}

const AnalysisWaitingPage: FC = () => {
  const router = useRouter()
  const analysisId = (router.params as { id?: string }).id || ''

  // ----- 数据 -----
  const [status, setStatus] = useState<AnalysisStatusResponse | null>(null)
  const [fatalError, setFatalError] = useState<string | null>(null)
  const [serverRemaining, setServerRemaining] = useState<number | null>(null)
  const [elapsedSec, setElapsedSec] = useState(0) // 从进入本页开始计
  const [tipIdx, setTipIdx] = useState(() => pickStartIndex())
  const [timedOut, setTimedOut] = useState(false)

  // refs（跨生命周期保持）
  const consecutiveErrorsRef = useRef(0)
  const lastKnownStatusRef = useRef<AnalysisStatusResponse['status'] | null>(null)
  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const secondTimerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const tipTimerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const pageActiveRef = useRef(true)
  const hasRedirectedRef = useRef(false)

  const clearCurrent = useAnalysisStore((s) => s.clearCurrent)

  /** 微信小程序：拉起「分析完成」类一次性订阅模板（`TARO_APP_SUBSCRIBE_TPL_ANALYSIS_DONE`）；未配置则跳过 */
  useEffect(() => {
    if (!analysisId) return
    if (process.env.TARO_ENV !== 'weapp') return
    const tid = SUBSCRIBE_TPL_ANALYSIS_DONE
    if (!tid) return
    void Taro.requestSubscribeMessage({ tmplIds: [tid] }).catch(() => {})
  }, [analysisId])

  // ---------------- 轮询核心 ----------------
  const poll = useCallback(async () => {
    if (!analysisId) return
    try {
      const s = await analysisService.getStatus(analysisId)
      consecutiveErrorsRef.current = 0
      lastKnownStatusRef.current = s.status
      setStatus(s)
      setServerRemaining(
        typeof s.estimated_remaining_seconds === 'number'
          ? Math.max(0, s.estimated_remaining_seconds)
          : null,
      )
      // 终态 -> 停止轮询
      if (s.status === 'completed') {
        if (!hasRedirectedRef.current) {
          hasRedirectedRef.current = true
          clearCurrent()
          // 小延时让最后一格"渲染分析报告"有机会亮起
          setTimeout(() => {
            Taro.reLaunch({ url: `/pages/analysis/report?id=${analysisId}` })
          }, COMPLETE_REDIRECT_MS)
        }
        return
      }
      if (s.status === 'failed') {
        return // UI 会基于 status.status 渲染失败界面
      }
    } catch (e) {
      if (isRequestError(e)) {
        if (e.kind === 'http_unauthorized') {
          setFatalError(e.message || '登录已失效，请重新登录')
          return
        }
        if (e.kind === 'business') {
          const toastTitle =
            (e.message && e.message.trim()) ||
            describeIntermittentRequestFailure(e).toastTitle
          setFatalError(e.message || '无法获取分析状态')
          Taro.showToast({ title: toastTitle, icon: 'none', duration: 2800 })
          return
        }
      }

      consecutiveErrorsRef.current += 1

      const { fatalMessage: fatalMsg, toastTitle } = describeIntermittentRequestFailure(e)

      if (consecutiveErrorsRef.current >= MAX_CONSECUTIVE_ERRORS) {
        setFatalError(fatalMsg)
        Taro.showToast({ title: toastTitle, icon: 'none' })
        return
      }
    }
    schedulePoll()
  }, [analysisId, clearCurrent]) // eslint-disable-line react-hooks/exhaustive-deps

  const schedulePoll = useCallback(() => {
    if (pollTimerRef.current) clearTimeout(pollTimerRef.current)
    if (!pageActiveRef.current) return
    pollTimerRef.current = setTimeout(() => {
      poll()
    }, pollDelayMs(lastKnownStatusRef.current))
  }, [poll])

  // 进入页 / useDidShow 时启动轮询
  const start = useCallback(() => {
    pageActiveRef.current = true
    poll() // 立即拉一次
  }, [poll])

  const pause = useCallback(() => {
    pageActiveRef.current = false
    if (pollTimerRef.current) {
      clearTimeout(pollTimerRef.current)
      pollTimerRef.current = null
    }
  }, [])

  // ---------------- 副作用：挂载/卸载/显隐 ----------------
  useEffect(() => {
    if (!analysisId) {
      setFatalError('缺少分析任务 ID，无法加载等待页')
      return
    }
    start()
    // 每秒推进本地时钟（用于剩余秒数、经过秒数、阶段推进）
    secondTimerRef.current = setInterval(() => {
      setElapsedSec((v) => v + 1)
      setServerRemaining((v) => (v === null || v <= 0 ? v : v - 1))
    }, 1000)
    tipTimerRef.current = setInterval(() => {
      setTipIdx((i) => (i + 1) % SWING_TIPS.length)
    }, TIPS_ROTATE_MS)

    return () => {
      if (pollTimerRef.current) clearTimeout(pollTimerRef.current)
      if (secondTimerRef.current) clearInterval(secondTimerRef.current)
      if (tipTimerRef.current) clearInterval(tipTimerRef.current)
    }
  }, [analysisId, start])

  useDidShow(() => {
    if (!analysisId) return
    // 回到前台时，若之前没到终态，重启轮询
    if (!hasRedirectedRef.current && status?.status !== 'failed') {
      start()
    }
  })

  useDidHide(() => {
    pause()
  })

  // 120s 超时占位
  useEffect(() => {
    if (elapsedSec >= TIMEOUT_FALLBACK_MS / 1000 && !timedOut && status?.status !== 'completed') {
      setTimedOut(true)
    }
  }, [elapsedSec, timedOut, status])

  // ---------------- 派生：当前阶段索引（W6-T4：完全以 backend 为准） ----------------
  const stageIndex = useMemo(() => {
    if (!status) return 0
    if (status.status === 'completed') return STAGES.length - 1
    if (status.status === 'failed') return -1
    return backendStageToIndex(status.stage)
  }, [status])

  // 展示用的剩余秒数：优先后端，否则按"总估 25s - 已过秒"兜底
  const displayRemaining = useMemo(() => {
    if (status?.status === 'completed') return 0
    if (status?.status === 'failed') return null
    if (serverRemaining !== null) return serverRemaining
    return Math.max(0, 22 - elapsedSec)
  }, [serverRemaining, elapsedSec, status])

  // ---------------- 事件 ----------------
  const handleRetryShoot = () => {
    clearCurrent()
    Taro.reLaunch({ url: '/pages/analysis/capture' })
  }
  const handleGoHome = () => {
    clearCurrent()
    Taro.reLaunch({ url: '/pages/index/index' })
  }

  // ---------------- 渲染 ----------------
  if (fatalError) {
    return (
      <View className='waiting waiting--error'>
        <Text className='waiting__error-icon'>📡</Text>
        <Text className='waiting__error-title'>{fatalError}</Text>
        <Button className='waiting__btn waiting__btn--primary' onClick={handleGoHome}>
          返回首页
        </Button>
      </View>
    )
  }

  if (status?.status === 'failed') {
    const err = status.error
    return (
      <View className='waiting waiting--failed'>
        <Text className='waiting__failed-icon'>😣</Text>
        <Text className='waiting__failed-title'>分析失败</Text>
        <Text className='waiting__failed-msg'>
          {err?.message || '抱歉，这次分析没能完成，请重新拍摄一次。'}
        </Text>
        {err?.quota_refunded && (
          <Text className='waiting__failed-refund'>✅ 本次已退回分析次数</Text>
        )}
        <View className='waiting__failed-actions'>
          <Button className='waiting__btn waiting__btn--primary' onClick={handleRetryShoot}>
            重新拍摄
          </Button>
          <Button className='waiting__btn waiting__btn--ghost' onClick={handleGoHome}>
            去首页
          </Button>
        </View>
      </View>
    )
  }

  const tip = SWING_TIPS[tipIdx]

  return (
    <View className='waiting'>
      {/* 顶部大动画 + 倒计时 */}
      <View className='waiting__hero'>
        <View className='waiting__spinner'>
          <View className='waiting__spinner-ring' />
          <View className='waiting__spinner-core'>
            <Text className='waiting__spinner-text'>AI</Text>
          </View>
        </View>
        <Text className='waiting__title'>
          {status?.status === 'completed' ? '分析完成' : 'AI 正在分析你的挥杆'}
        </Text>
        <Text className='waiting__countdown'>
          {status?.status === 'completed'
            ? '即将为你打开报告…'
            : displayRemaining !== null
              ? `预计还需 ${displayRemaining} 秒`
              : '预计还需不到 30 秒'}
        </Text>
      </View>

      {elapsedSec >= SOFT_LONG_WAIT_SEC &&
        !timedOut &&
        status?.status !== 'completed' &&
        (
          <View className='waiting__soft-wait'>
            <Text className='waiting__soft-wait-text'>
              分析可能比预期稍久，请耐心等待；仍可留在本页或稍后在「我的分析报告」查看结果。
            </Text>
          </View>
        )}

      {/* 阶段列表 */}
      <View className='waiting__stages'>
        {STAGES.map((s, idx) => {
          const done = idx < stageIndex
          const active = idx === stageIndex && status?.status !== 'completed'
          const completed = status?.status === 'completed'
          return (
            <View
              key={s.key}
              className={[
                'waiting__stage',
                done || completed ? 'waiting__stage--done' : '',
                active ? 'waiting__stage--active' : '',
              ]
                .filter(Boolean)
                .join(' ')}
            >
              <View className='waiting__stage-dot'>
                {done || completed ? <Text>✓</Text> : active ? <View className='waiting__stage-pulse' /> : null}
              </View>
              <Text className='waiting__stage-label'>{s.label}</Text>
            </View>
          )
        })}
      </View>

      {/* 超时占位 */}
      {timedOut && status?.status !== 'completed' && (
        <View className='waiting__timeout'>
          <Text className='waiting__timeout-title'>⏳ 分析时间比预期长</Text>
          <Text className='waiting__timeout-desc'>
            别担心，任务还在后台跑。完成后我们会通过微信通知你（功能上线中）。
            你也可以先去首页做点别的。
          </Text>
          <Button className='waiting__btn waiting__btn--ghost' onClick={handleGoHome}>
            先回首页
          </Button>
        </View>
      )}

      {/* 小贴士 */}
      <View className='waiting__tip'>
        <View className='waiting__tip-header'>
          <Text className='waiting__tip-cat'>{tip.category}</Text>
          <Text className='waiting__tip-title'>你知道吗？</Text>
        </View>
        <Text className='waiting__tip-text'>{tip.text}</Text>
      </View>
    </View>
  )
}

export default AnalysisWaitingPage
