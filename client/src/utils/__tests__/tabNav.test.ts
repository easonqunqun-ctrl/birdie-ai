/**
 * tabNav.ts 单测：tabBar 跨页上下文一次性消费语义
 *
 * 核心契约：
 *  - switchToCoach 带 ctx 时先写 storage、再 switchTab
 *  - consumeCoachPendingContext 取一次后必须立刻清掉 storage（一次性）
 *  - switchToCoach 不带 ctx 时不写 storage（避免覆盖上次未消费的 ctx）
 */

import Taro from '@tarojs/taro'
import {
  switchToCoach,
  switchToHome,
  switchToTraining,
  switchToProfile,
  switchToCoachWithSession,
  consumeCoachPendingContext,
  toastTabNavigationFailure,
} from '@/utils/tabNav'

const T = Taro as unknown as Record<string, jest.Mock>

const COACH_CTX_KEY = 'tab_pending_coach_context'

beforeEach(() => {
  ;(Taro as any).clearStorageSync()
  T.switchTab.mockClear()
  T.showToast.mockClear()
})

describe('switchToCoach', () => {
  test('带 analysisId → 写 storage + switchTab', async () => {
    await switchToCoach({ analysisId: 'a1' })
    expect(Taro.getStorageSync(COACH_CTX_KEY)).toEqual({ analysisId: 'a1' })
    expect(T.switchTab).toHaveBeenCalledWith({ url: '/pages/coach/index' })
  })

  test('带 prefill → 写 storage', async () => {
    await switchToCoach({ prefill: '我想问挥杆顶点' })
    expect((Taro.getStorageSync(COACH_CTX_KEY) as any).prefill).toBe('我想问挥杆顶点')
  })

  test('不带 ctx → 不写 storage（避免覆盖未消费上下文）', async () => {
    // 先写一份
    Taro.setStorageSync(COACH_CTX_KEY, { analysisId: 'old' })
    await switchToCoach()
    expect(Taro.getStorageSync(COACH_CTX_KEY)).toEqual({ analysisId: 'old' })
  })

  test('空对象 → 也不应写（无 analysisId/prefill/sessionId）', async () => {
    await switchToCoach({})
    expect(Taro.getStorageSync(COACH_CTX_KEY)).toBe('') // mock 默认空串
  })
})

describe('consumeCoachPendingContext · 一次性语义', () => {
  test('读出后立即清空', () => {
    Taro.setStorageSync(COACH_CTX_KEY, { analysisId: 'a1' })
    const ctx = consumeCoachPendingContext()
    expect(ctx).toEqual({ analysisId: 'a1' })
    expect(consumeCoachPendingContext()).toBeNull() // 第二次为 null
  })

  test('无 ctx → 返回 null', () => {
    expect(consumeCoachPendingContext()).toBeNull()
  })

  test('storage 中是非对象（脏数据）→ null', () => {
    Taro.setStorageSync(COACH_CTX_KEY, 'corrupted-string')
    expect(consumeCoachPendingContext()).toBeNull()
  })
})

describe('switchToCoachWithSession', () => {
  test('写入 sessionId + contextAnalysisId 后 switchTab', async () => {
    await switchToCoachWithSession('s1', 'a1')
    const ctx = Taro.getStorageSync(COACH_CTX_KEY) as any
    expect(ctx.sessionId).toBe('s1')
    expect(ctx.contextAnalysisId).toBe('a1')
    expect(T.switchTab).toHaveBeenCalledWith({ url: '/pages/coach/index' })
  })

  test('contextAnalysisId 不传 → undefined', async () => {
    await switchToCoachWithSession('s1')
    const ctx = Taro.getStorageSync(COACH_CTX_KEY) as any
    expect(ctx.sessionId).toBe('s1')
    expect(ctx.contextAnalysisId).toBeUndefined()
  })
})

describe('其它快捷 tab 入口', () => {
  test.each([
    [switchToHome, '/pages/index/index'],
    [switchToTraining, '/pages/training/index'],
    [switchToProfile, '/pages/profile/index'],
  ])('%s → switchTab(%s)', async (fn, expected) => {
    await fn()
    expect(T.switchTab).toHaveBeenCalledWith({ url: expected })
  })
})

describe('toastTabNavigationFailure', () => {
  test('网络错误 → toast 通用「网络异常」', () => {
    toastTabNavigationFailure(new Error('boom'))
    expect(T.showToast).toHaveBeenCalledTimes(1)
    const call = T.showToast.mock.calls[0][0]
    expect(call.icon).toBe('none')
    expect(call.title).toMatch(/网络/)
  })
})
