/**
 * privacy.ts 单测：微信隐私授权守卫（wx.getPrivacySetting + requirePrivacyAuthorize）
 *
 * 重点：
 *  - 非 weapp / 老基础库：no-op，不抛
 *  - needAuthorization=false：直接通过
 *  - needAuthorization=true：弹窗，用户拒绝 → PrivacyDeniedError
 */

import { ensurePrivacyAuthorized, PrivacyDeniedError } from '@/utils/privacy'

declare global {
  // eslint-disable-next-line no-var, @typescript-eslint/no-explicit-any
  var wx: any
}

function installWxWithPrivacy(opts: {
  needAuthorization: boolean
  requireResult: 'success' | 'fail'
}) {
  globalThis.wx = {
    canIUse: jest.fn((api: string) =>
      api === 'getPrivacySetting' || api === 'requirePrivacyAuthorize',
    ),
    getPrivacySetting: jest.fn(({ success }: any) =>
      success({ needAuthorization: opts.needAuthorization }),
    ),
    requirePrivacyAuthorize: jest.fn(({ success, fail }: any) => {
      if (opts.requireResult === 'success') success()
      else fail({ errMsg: 'requirePrivacyAuthorize:fail' })
    }),
  }
}

afterEach(() => {
  delete (globalThis as any).wx
})

describe('ensurePrivacyAuthorized', () => {
  test('非 weapp 环境直接 no-op', async () => {
    const origTaroEnv = process.env.TARO_ENV
    process.env.TARO_ENV = 'h5'
    try {
      await expect(ensurePrivacyAuthorized('login')).resolves.toBeUndefined()
    } finally {
      process.env.TARO_ENV = origTaroEnv
    }
  })

  test('wx 缺失 → no-op', async () => {
    delete (globalThis as any).wx
    await expect(ensurePrivacyAuthorized('chooseMedia')).resolves.toBeUndefined()
  })

  test('canIUse 返回 false → no-op', async () => {
    globalThis.wx = {
      canIUse: jest.fn(() => false),
      getPrivacySetting: jest.fn(),
      requirePrivacyAuthorize: jest.fn(),
    }
    await expect(ensurePrivacyAuthorized('login')).resolves.toBeUndefined()
    expect(globalThis.wx.getPrivacySetting).not.toHaveBeenCalled()
  })

  test('needAuthorization=false → 不触发弹窗', async () => {
    installWxWithPrivacy({ needAuthorization: false, requireResult: 'success' })
    await expect(ensurePrivacyAuthorized('login')).resolves.toBeUndefined()
    expect(globalThis.wx.getPrivacySetting).toHaveBeenCalledTimes(1)
    expect(globalThis.wx.requirePrivacyAuthorize).not.toHaveBeenCalled()
  })

  test('needAuthorization=true + 用户同意 → resolve', async () => {
    installWxWithPrivacy({ needAuthorization: true, requireResult: 'success' })
    await expect(ensurePrivacyAuthorized('chooseMedia')).resolves.toBeUndefined()
    expect(globalThis.wx.requirePrivacyAuthorize).toHaveBeenCalledTimes(1)
  })

  test('needAuthorization=true + 用户拒绝 → PrivacyDeniedError', async () => {
    installWxWithPrivacy({ needAuthorization: true, requireResult: 'fail' })
    await expect(ensurePrivacyAuthorized('login')).rejects.toBeInstanceOf(
      PrivacyDeniedError,
    )
  })

  test('getPrivacySetting fail → 抛带 errMsg 的 Error', async () => {
    globalThis.wx = {
      canIUse: jest.fn(() => true),
      getPrivacySetting: jest.fn(({ fail }: any) =>
        fail({ errMsg: 'getPrivacySetting:fail something' }),
      ),
      requirePrivacyAuthorize: jest.fn(),
    }
    await expect(ensurePrivacyAuthorized('login')).rejects.toThrow(
      'getPrivacySetting:fail something',
    )
  })
})

describe('PrivacyDeniedError', () => {
  test('携带 apiName 与可读 message', () => {
    const err = new PrivacyDeniedError('chooseMedia')
    expect(err.name).toBe('PrivacyDeniedError')
    expect(err.apiName).toBe('chooseMedia')
    expect(err.message).toContain('chooseMedia')
  })
})
