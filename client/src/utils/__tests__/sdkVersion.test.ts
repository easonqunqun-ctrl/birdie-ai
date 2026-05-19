/**
 * sdkVersion.ts 单测：compareSemver + checkMinSdkVersion 分支
 *
 * 锁定：低于 MIN_SDK_VERSION 必须弹 modal 提示；非 weapp 环境必须 no-op。
 */

import Taro from '@tarojs/taro'
import {
  compareSemver,
  checkMinSdkVersion,
  MIN_SDK_VERSION,
} from '@/utils/sdkVersion'

const T = Taro as unknown as Record<string, jest.Mock>

const origTaroEnv = process.env.TARO_ENV
afterEach(() => {
  delete (globalThis as any).wx
  process.env.TARO_ENV = origTaroEnv
  T.showModal.mockClear()
})

describe('compareSemver', () => {
  test.each([
    ['1.0.0', '1.0.0', 0],
    ['1.2.3', '1.2.2', 1],
    ['1.2.2', '1.2.3', -1],
    ['2.0.0', '1.99.99', 1],
    ['1.0', '1.0.0', 0], // 短版本号被视为补 0
    ['2.27.1', MIN_SDK_VERSION, 0],
    ['2.26.0', MIN_SDK_VERSION, -1],
  ])('compareSemver(%s, %s) = %s', (a, b, expected) => {
    expect(compareSemver(a, b)).toBe(expected)
  })

  test('非数字段视为 0', () => {
    expect(compareSemver('a.b.c', '0.0.0')).toBe(0)
    expect(compareSemver('1.x.0', '1.0.0')).toBe(0)
  })
})

describe('checkMinSdkVersion', () => {
  test('非 weapp 环境 → 直接 true，不读 wx', () => {
    process.env.TARO_ENV = 'h5'
    expect(checkMinSdkVersion()).toBe(true)
    expect(T.showModal).not.toHaveBeenCalled()
  })

  test('weapp + SDK ≥ MIN → true，不弹 modal', () => {
    process.env.TARO_ENV = 'weapp'
    ;(globalThis as any).wx = {
      canIUse: jest.fn(() => true),
      getAppBaseInfo: jest.fn(() => ({ SDKVersion: '3.0.0' })),
    }
    expect(checkMinSdkVersion()).toBe(true)
    expect(T.showModal).not.toHaveBeenCalled()
  })

  test('weapp + SDK < MIN → false 并弹 modal', () => {
    process.env.TARO_ENV = 'weapp'
    ;(globalThis as any).wx = {
      canIUse: jest.fn(() => true),
      getAppBaseInfo: jest.fn(() => ({ SDKVersion: '2.10.0' })),
    }
    expect(checkMinSdkVersion()).toBe(false)
    expect(T.showModal).toHaveBeenCalledTimes(1)
    const arg = T.showModal.mock.calls[0][0]
    expect(arg.title).toBe('微信版本过低')
    expect(arg.content).toContain('2.10.0')
    expect(arg.showCancel).toBe(false)
  })

  test('weapp 老基础库（无 getAppBaseInfo）→ 退回 getSystemInfoSync', () => {
    process.env.TARO_ENV = 'weapp'
    ;(globalThis as any).wx = {
      canIUse: jest.fn(() => false),
    }
    T.getSystemInfoSync.mockReturnValueOnce({ SDKVersion: '2.30.0', platform: 'devtools' })
    expect(checkMinSdkVersion()).toBe(true)
  })

  test('拿不到 SDKVersion → 不阻塞，返回 true', () => {
    process.env.TARO_ENV = 'weapp'
    ;(globalThis as any).wx = {
      canIUse: jest.fn(() => true),
      getAppBaseInfo: jest.fn(() => ({})),
    }
    expect(checkMinSdkVersion()).toBe(true)
  })

  test('抛异常 → 不阻塞主流程', () => {
    process.env.TARO_ENV = 'weapp'
    ;(globalThis as any).wx = {
      canIUse: jest.fn(() => {
        throw new Error('boom')
      }),
    }
    expect(checkMinSdkVersion()).toBe(true)
  })
})
