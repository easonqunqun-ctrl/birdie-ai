import Taro from '@tarojs/taro'
import {
  getCurrentGcj02Location,
  LocationError,
  promptOpenLocationSettings,
} from '@/adapters/location'
import { ensurePrivacyAuthorized, PrivacyDeniedError } from '@/utils/privacy'

jest.mock('@/utils/privacy', () => ({
  ensurePrivacyAuthorized: jest.fn(() => Promise.resolve()),
  PrivacyDeniedError: class PrivacyDeniedError extends Error {
    name = 'PrivacyDeniedError'
    constructor(mockApiName: string) {
      super(`用户拒绝了隐私授权：${mockApiName}`)
    }
  },
}))

describe('location adapter', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    ;(Taro.getSetting as jest.Mock).mockResolvedValue({
      authSetting: { 'scope.userLocation': true },
    })
    ;(Taro.getLocation as jest.Mock).mockResolvedValue({
      latitude: 31.2,
      longitude: 121.5,
    })
  })

  test('已授权时返回 GCJ-02 坐标', async () => {
    const loc = await getCurrentGcj02Location()
    expect(loc).toEqual({ latitude: 31.2, longitude: 121.5 })
    expect(ensurePrivacyAuthorized).toHaveBeenCalledWith('getLocation')
    expect(Taro.getLocation).toHaveBeenCalledWith(
      expect.objectContaining({ type: 'gcj02' }),
    )
  })

  test('用户曾拒绝 scope.userLocation → denied', async () => {
    ;(Taro.getSetting as jest.Mock).mockResolvedValue({
      authSetting: { 'scope.userLocation': false },
    })
    await expect(getCurrentGcj02Location()).rejects.toMatchObject({
      code: 'denied',
    })
    expect(Taro.getLocation).not.toHaveBeenCalled()
  })

  test('getLocation auth deny → denied', async () => {
    ;(Taro.getLocation as jest.Mock).mockRejectedValue({
      errMsg: 'getLocation:fail auth deny',
    })
    await expect(getCurrentGcj02Location()).rejects.toMatchObject({
      code: 'denied',
    })
  })

  test('隐私协议拒绝 → denied', async () => {
    ;(ensurePrivacyAuthorized as jest.Mock).mockRejectedValue(
      new PrivacyDeniedError('getLocation'),
    )
    await expect(getCurrentGcj02Location()).rejects.toMatchObject({
      code: 'denied',
    })
  })

  test('promptOpenLocationSettings 确认后打开设置页', async () => {
    ;(Taro.showModal as jest.Mock).mockResolvedValue({ confirm: true, cancel: false })
    const ok = await promptOpenLocationSettings()
    expect(ok).toBe(true)
    expect(Taro.openSetting).toHaveBeenCalled()
  })
})
