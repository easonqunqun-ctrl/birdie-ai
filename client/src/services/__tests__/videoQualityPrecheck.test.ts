/**
 * @jest-environment node
 */

import type TaroType from '@tarojs/taro'

type Taro = typeof TaroType

interface LoadResult {
  confirmQualityWarningsIfNeeded: typeof import('@/services/videoQualityPrecheck').confirmQualityWarningsIfNeeded
  showQualityBlockModal: typeof import('@/services/videoQualityPrecheck').showQualityBlockModal
  Taro: Taro
}

async function loadModule(): Promise<LoadResult> {
  jest.resetModules()
  const Taro = (await import('@tarojs/taro')).default
  const { confirmQualityWarningsIfNeeded, showQualityBlockModal } = await import(
    '@/services/videoQualityPrecheck'
  )
  return { confirmQualityWarningsIfNeeded, showQualityBlockModal, Taro }
}

beforeEach(() => {
  jest.resetModules()
})

describe('confirmQualityWarningsIfNeeded', () => {
  test('无警告 → 直接 true，不弹窗', async () => {
    const { confirmQualityWarningsIfNeeded, Taro } = await loadModule()
    await expect(confirmQualityWarningsIfNeeded([])).resolves.toBe(true)
    expect(Taro.showModal).not.toHaveBeenCalled()
  })

  test('有警告 → 弹窗；用户确认继续', async () => {
    const { confirmQualityWarningsIfNeeded, Taro } = await loadModule()
    ;(Taro.showModal as jest.Mock).mockResolvedValueOnce({ confirm: true, cancel: false })
    await expect(confirmQualityWarningsIfNeeded(['low_light'])).resolves.toBe(true)
    expect(Taro.showModal).toHaveBeenCalledWith(
      expect.objectContaining({
        title: '拍摄质量提示',
        confirmText: '仍要继续',
        cancelText: '重新拍摄',
      }),
    )
  })

  test('有警告 → 用户取消', async () => {
    const { confirmQualityWarningsIfNeeded, Taro } = await loadModule()
    ;(Taro.showModal as jest.Mock).mockResolvedValueOnce({ confirm: false, cancel: true })
    await expect(confirmQualityWarningsIfNeeded(['camera_shake'])).resolves.toBe(false)
  })
})

describe('showQualityBlockModal', () => {
  test('无阻断码 → 不弹窗', async () => {
    const { showQualityBlockModal, Taro } = await loadModule()
    await showQualityBlockModal([])
    expect(Taro.showModal).not.toHaveBeenCalled()
  })

  test('有阻断码 → 仅确认重拍', async () => {
    const { showQualityBlockModal, Taro } = await loadModule()
    await showQualityBlockModal(['too_dark', 'too_shaky'])
    expect(Taro.showModal).toHaveBeenCalledWith(
      expect.objectContaining({
        title: '无法开始分析',
        showCancel: false,
        confirmText: '重新拍摄',
      }),
    )
  })
})
