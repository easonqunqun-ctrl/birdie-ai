/**
 * tabBar 页面跳转上下文传递（W8-T2）
 *
 * 背景：
 *   W8-T2 正式启用 tabBar（首页 / AI 教练 / 训练 / 我的）后，跳转到 tabBar
 *   页必须用 `Taro.switchTab`，但 `switchTab` **不允许带 URL query**。
 *   W7 场景里"从报告页点问 AI 教练"会把 `analysis_id` / `prefill` 带过去，
 *   这类"跨页上下文"需要换成另一条通道：
 *     - 发起页调 `switchToCoach({ analysisId, prefill })` 先写 storage，再 switchTab
 *     - 目标 tab 页在 `onShow` 里调 `consumeCoachPendingContext()` 消费一次后清掉
 *
 *   与直接用 storage 的区别：consumer API 是一次性的，避免用户在 tab 之间
 *   反复切换时重复吃同一份"历史上下文"。
 */

import Taro from '@tarojs/taro'
import { getStorageSync, removeStorageSync, setStorageSync } from '@/adapters/kvStorage'
import { describeIntermittentRequestFailure } from '@/services/request'

const COACH_CTX_KEY = 'tab_pending_coach_context'

/** tabBar switchTab reject（页面未注册 / 宿主异常）时兜底 toast */
export function toastTabNavigationFailure(err: unknown): void {
  Taro.showToast({
    title: describeIntermittentRequestFailure(err).toastTitle,
    icon: 'none',
  })
}

export interface CoachPendingContext {
  /** 报告 ID，用于让 coach session 注入最近一次分析 */
  analysisId?: string
  /** 输入框预填文案（明文，无需再编码） */
  prefill?: string
  /** 从「对话历史」进入时恢复已有会话 */
  sessionId?: string
  contextAnalysisId?: string | null
}

/**
 * 切到 AI 教练 tab，可选携带上下文。
 *
 * @returns 由 `Taro.switchTab` 透传的 Promise（失败时 reject，调用方可自行兜底）
 */
export function switchToCoach(ctx?: CoachPendingContext) {
  if (ctx && (ctx.analysisId || ctx.prefill || ctx.sessionId)) {
    setStorageSync(COACH_CTX_KEY, ctx)
  }
  return Taro.switchTab({ url: '/pages/coach/index' })
}

/**
 * 取出并清空 pending context（一次性消费）。
 * tabBar 页的 `useDidShow` / `onShow` 里调用。
 */
export function consumeCoachPendingContext(): CoachPendingContext | null {
  const raw = getStorageSync(COACH_CTX_KEY)
  if (!raw || typeof raw !== 'object') return null
  removeStorageSync(COACH_CTX_KEY)
  return raw as CoachPendingContext
}

/** 无上下文的快捷入口 */
export function switchToHome() {
  return Taro.switchTab({ url: '/pages/index/index' })
}

export function switchToTraining() {
  return Taro.switchTab({ url: '/pages/training/index' })
}

export function switchToProfile() {
  return Taro.switchTab({ url: '/pages/profile/index' })
}

/** 从对话历史等入口打开 AI 教练并加载指定 session */
export function switchToCoachWithSession(
  sessionId: string,
  contextAnalysisId?: string | null,
) {
  setStorageSync(COACH_CTX_KEY, {
    sessionId,
    contextAnalysisId: contextAnalysisId ?? undefined,
  } as CoachPendingContext)
  return Taro.switchTab({ url: '/pages/coach/index' })
}
