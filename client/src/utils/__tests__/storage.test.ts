/**
 * storage.ts 单测：Token / User / 协议同意 / 引导标记 / clearAuth 范围
 *
 * 重点：clearAuthSession 不能误删 `agreed_terms`、`analysis_guide_seen`
 * （AGENTS.md & docs/06 合规体验底线）
 */

import Taro from '@tarojs/taro'
import { storage, CURRENT_TERMS_VERSION } from '@/utils/storage'

const T = Taro as unknown as Record<string, jest.Mock>

beforeEach(() => {
  ;(Taro as any).clearStorageSync()
})

describe('storage · Token', () => {
  test('setToken / getToken / clearToken round-trip', () => {
    expect(storage.getToken()).toBe('')
    storage.setToken('jwt_abc')
    expect(storage.getToken()).toBe('jwt_abc')
    storage.clearToken()
    expect(storage.getToken()).toBe('')
  })
})

describe('storage · User', () => {
  test('setUser / getUser 支持泛型对象', () => {
    expect(storage.getUser()).toBeNull()
    storage.setUser({ id: 1, nickname: '小鸟' })
    expect(storage.getUser<{ id: number }>()).toEqual({ id: 1, nickname: '小鸟' })
    storage.clearUser()
    expect(storage.getUser()).toBeNull()
  })
})

describe('storage · 分析引导标记', () => {
  test('首次为 false，标记后为 true', () => {
    expect(storage.hasSeenAnalysisGuide()).toBe(false)
    storage.markAnalysisGuideSeen()
    expect(storage.hasSeenAnalysisGuide()).toBe(true)
  })
})

describe('storage · 用户协议同意（合规底线）', () => {
  test('未同意 → null', () => {
    expect(storage.getAgreedTerms()).toBeNull()
    expect(storage.hasAgreedCurrentTerms()).toBe(false)
  })

  test('记下当前版本 → hasAgreedCurrentTerms 为 true', () => {
    storage.setAgreedTerms(CURRENT_TERMS_VERSION)
    const rec = storage.getAgreedTerms()
    expect(rec).not.toBeNull()
    expect(rec!.version).toBe(CURRENT_TERMS_VERSION)
    expect(typeof rec!.agreedAt).toBe('number')
    expect(storage.hasAgreedCurrentTerms()).toBe(true)
  })

  test('记下旧版本 → hasAgreedCurrentTerms 为 false（强制再次同意）', () => {
    storage.setAgreedTerms('v0.0.1')
    expect(storage.hasAgreedCurrentTerms()).toBe(false)
  })

  test('被外部写脏的 record 应被忽略', () => {
    ;(Taro as any).setStorageSync('agreed_terms', 'corrupted')
    expect(storage.getAgreedTerms()).toBeNull()
    ;(Taro as any).setStorageSync('agreed_terms', { version: 'v1' /* 缺 agreedAt */ })
    expect(storage.getAgreedTerms()).toBeNull()
  })
})

describe('storage · clearAuthSession 范围（防误删合规标记）', () => {
  test('只清 token + user，保留协议同意与引导标记', () => {
    storage.setToken('t')
    storage.setUser({ id: 1 })
    storage.setAgreedTerms(CURRENT_TERMS_VERSION)
    storage.markAnalysisGuideSeen()

    storage.clearAuthSession()

    expect(storage.getToken()).toBe('')
    expect(storage.getUser()).toBeNull()
    expect(storage.hasAgreedCurrentTerms()).toBe(true)
    expect(storage.hasSeenAnalysisGuide()).toBe(true)
  })

  test('clearAll 会清掉所有，包括协议同意', () => {
    storage.setToken('t')
    storage.setAgreedTerms(CURRENT_TERMS_VERSION)
    storage.markAnalysisGuideSeen()

    storage.clearAll()

    expect(storage.getToken()).toBe('')
    expect(storage.hasAgreedCurrentTerms()).toBe(false)
    expect(storage.hasSeenAnalysisGuide()).toBe(false)
  })
})

describe('storage · 仅调用 Taro 真实 API', () => {
  test('setToken 走 Taro.setStorageSync', () => {
    storage.setToken('x')
    expect(T.setStorageSync).toHaveBeenCalledWith('auth_token', 'x')
  })
  test('clearToken 走 Taro.removeStorageSync', () => {
    storage.clearToken()
    expect(T.removeStorageSync).toHaveBeenCalledWith('auth_token')
  })
})
