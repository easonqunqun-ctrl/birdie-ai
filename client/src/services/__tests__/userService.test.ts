/**
 * userService.ts 单测：身份与 onboarding 接口的端分叉与 querystring 拼接
 *
 * 关键守护：
 *  - weapp 走 /auth/wechat-login，rn 走 /auth/wechat-open-login（端分叉）
 *  - wechatLogin / refreshToken / getMe 全部应放宽超时（60s）以容忍真机弱网
 *  - 注销账号 confirm_text 必须按 raw 文本透传给后端校验
 */

import { userService } from '@/services/userService'
import Taro from '@tarojs/taro'

const T = Taro as unknown as Record<string, jest.Mock>
const ok = (data: unknown) => ({
  statusCode: 200,
  data: { code: 0, message: 'ok', data },
})

const origTaroEnv = process.env.TARO_ENV

beforeEach(() => {
  ;(Taro as any).clearStorageSync()
  T.request.mockReset()
})

afterAll(() => {
  process.env.TARO_ENV = origTaroEnv
})

describe('userService.wechatLogin · 端分叉', () => {
  test('weapp → /auth/wechat-login', async () => {
    process.env.TARO_ENV = 'weapp'
    T.request.mockResolvedValueOnce(ok({ token: 't', user: {} }))
    await userService.wechatLogin({ code: 'wxcode' } as any)
    const sent = T.request.mock.calls[0][0]
    expect(sent.url).toContain('/auth/wechat-login')
    expect(sent.url).not.toContain('wechat-open-login')
    expect(sent.header.Authorization).toBeUndefined() // noAuth
    expect(sent.timeout).toBeGreaterThanOrEqual(60000)
  })

  test('rn → /auth/wechat-open-login', async () => {
    process.env.TARO_ENV = 'rn'
    T.request.mockResolvedValueOnce(ok({ token: 't', user: {} }))
    await userService.wechatLogin({ access_token: 'at' } as any)
    const sent = T.request.mock.calls[0][0]
    expect(sent.url).toContain('/auth/wechat-open-login')
  })
})

describe('userService.refreshToken / getMe', () => {
  test('refreshToken → POST /auth/refresh-token', async () => {
    T.request.mockResolvedValueOnce(ok({ token: 't', expires_in: 7200 }))
    await userService.refreshToken()
    const sent = T.request.mock.calls[0][0]
    expect(sent.method).toBe('POST')
    expect(sent.url).toContain('/auth/refresh-token')
  })

  test('getMe → GET /users/me', async () => {
    T.request.mockResolvedValueOnce(ok({ id: 1 }))
    await userService.getMe()
    const sent = T.request.mock.calls[0][0]
    expect(sent.method).toBe('GET')
    expect(sent.url).toContain('/users/me')
    expect(sent.timeout).toBeGreaterThanOrEqual(60000)
  })
})

describe('userService.completeOnboarding / updateMe', () => {
  test('completeOnboarding → POST /users/me/onboarding', async () => {
    T.request.mockResolvedValueOnce(ok({ id: 1 }))
    await userService.completeOnboarding({ handicap: 10 } as any)
    const sent = T.request.mock.calls[0][0]
    expect(sent.method).toBe('POST')
    expect(sent.url).toContain('/users/me/onboarding')
    expect(sent.data).toEqual({ handicap: 10 })
  })

  test('updateMe → PATCH /users/me', async () => {
    T.request.mockResolvedValueOnce(ok({ id: 1 }))
    await userService.updateMe({ nickname: '小鸟' } as any)
    const sent = T.request.mock.calls[0][0]
    expect(sent.method).toBe('PATCH')
    expect(sent.url).toContain('/users/me')
  })
})

describe('userService 注销账号 · confirm_text 透传', () => {
  test('requestAccountDeletion 把 confirmText 装进 body.confirm_text', async () => {
    T.request.mockResolvedValueOnce(ok({ id: 1 }))
    await userService.requestAccountDeletion('我确认注销')
    const sent = T.request.mock.calls[0][0]
    expect(sent.url).toContain('/users/me/account-deletion')
    expect(sent.data).toEqual({ confirm_text: '我确认注销' })
  })

  test('cancelAccountDeletion → POST /users/me/account-deletion/cancel', async () => {
    T.request.mockResolvedValueOnce(ok({ id: 1 }))
    await userService.cancelAccountDeletion()
    const sent = T.request.mock.calls[0][0]
    expect(sent.url).toContain('/users/me/account-deletion/cancel')
    expect(sent.data).toEqual({})
  })
})

describe('userService.getAnalysisProgress · querystring', () => {
  test('未传 windowDays → 不拼 ?', async () => {
    T.request.mockResolvedValueOnce(ok({ points: [] }))
    await userService.getAnalysisProgress()
    expect(T.request.mock.calls[0][0].url).toBe(
      'http://localhost:8000/v1/users/me/analysis-progress',
    )
  })

  test('windowDays=30 → ?window_days=30', async () => {
    T.request.mockResolvedValueOnce(ok({ points: [] }))
    await userService.getAnalysisProgress(30)
    expect(T.request.mock.calls[0][0].url).toContain('?window_days=30')
  })

  test('windowDays=0 视为无效 → 不拼 ?', async () => {
    T.request.mockResolvedValueOnce(ok({ points: [] }))
    await userService.getAnalysisProgress(0)
    expect(T.request.mock.calls[0][0].url).not.toContain('?')
  })

  test('windowDays=-5 视为无效 → 不拼 ?', async () => {
    T.request.mockResolvedValueOnce(ok({ points: [] }))
    await userService.getAnalysisProgress(-5)
    expect(T.request.mock.calls[0][0].url).not.toContain('?')
  })
})
