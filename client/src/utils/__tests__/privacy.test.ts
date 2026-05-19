/**
 * privacy.ts 单测：微信隐私授权守卫（wx.getPrivacySetting + requirePrivacyAuthorize）
 *
 * 重点：
 *  - 非 weapp / 老基础库：no-op，不抛
 *  - needAuthorization=false：直接通过
 *  - needAuthorization=true：弹窗，用户拒绝 → PrivacyDeniedError
 */

import { ensurePrivacyAuthorized, PrivacyDeniedError } from '@/utils/privacy'

type WxMock = {
  canIUse: jest.Mock
  getPrivacySetting: jest.Mock
  requirePrivacyAuthorize: jest.Mock
}

function setWx(mock: WxMock) {
  ;(globalThis as unknown as { wx: WxMock }).wx = mock
}

function getWx(): WxMock {
  return (globalThis as unknown as { wx: WxMock }).wx
}

function clearWx() {
  delete (globalThis as unknown as { wx?: WxMock }).wx
}

function installWxWithPrivacy(opts: {
  needAuthorization: boolean
  requireResult: 'success' | 'fail'
}) {
  setWx({
    canIUse: jest.fn((api: string) =>
      api === 'getPrivacySetting' || api === 'requirePrivacyAuthorize',
    ),
    getPrivacySetting: jest.fn(({ success }: { success: (r: unknown) => void }) =>
      success({ needAuthorization: opts.needAuthorization }),
    ),
    requirePrivacyAuthorize: jest.fn(
      ({ success, fail }: { success: () => void; fail: (e: unknown) => void }) => {
        if (opts.requireResult === 'success') success()
        else fail({ errMsg: 'requirePrivacyAuthorize:fail' })
      },
    ),
  })
}

afterEach(() => {
  clearWx()
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
    clearWx()
    await expect(ensurePrivacyAuthorized('chooseMedia')).resolves.toBeUndefined()
  })

  test('canIUse 返回 false → no-op', async () => {
    setWx({
      canIUse: jest.fn(() => false),
      getPrivacySetting: jest.fn(),
      requirePrivacyAuthorize: jest.fn(),
    })
    await expect(ensurePrivacyAuthorized('login')).resolves.toBeUndefined()
    expect(getWx().getPrivacySetting).not.toHaveBeenCalled()
  })

  test('needAuthorization=false → 不触发弹窗', async () => {
    installWxWithPrivacy({ needAuthorization: false, requireResult: 'success' })
    await expect(ensurePrivacyAuthorized('login')).resolves.toBeUndefined()
    expect(getWx().getPrivacySetting).toHaveBeenCalledTimes(1)
    expect(getWx().requirePrivacyAuthorize).not.toHaveBeenCalled()
  })

  test('needAuthorization=true + 用户同意 → resolve', async () => {
    installWxWithPrivacy({ needAuthorization: true, requireResult: 'success' })
    await expect(ensurePrivacyAuthorized('chooseMedia')).resolves.toBeUndefined()
    expect(getWx().requirePrivacyAuthorize).toHaveBeenCalledTimes(1)
  })

  test('needAuthorization=true + 用户拒绝 → PrivacyDeniedError', async () => {
    installWxWithPrivacy({ needAuthorization: true, requireResult: 'fail' })
    await expect(ensurePrivacyAuthorized('login')).rejects.toBeInstanceOf(
      PrivacyDeniedError,
    )
  })

  test('getPrivacySetting fail → 抛带 errMsg 的 Error', async () => {
    setWx({
      canIUse: jest.fn(() => true),
      getPrivacySetting: jest.fn(({ fail }: { fail: (e: unknown) => void }) =>
        fail({ errMsg: 'getPrivacySetting:fail something' }),
      ),
      requirePrivacyAuthorize: jest.fn(),
    })
    await expect(ensurePrivacyAuthorized('login')).rejects.toThrow(
      'getPrivacySetting:fail something',
    )
  })
})
