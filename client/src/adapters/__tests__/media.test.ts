/**
 * media adapter：小程序端行为单测。
 * （原 RN picker 分支已移除，App 端改用独立 Flutter 工程。）
 */

const originalEnv = process.env.TARO_ENV

afterEach(() => {
  process.env.TARO_ENV = originalEnv
  jest.resetModules()
})

describe('getCapturePlatformTips', () => {
  test('weapp → 空', async () => {
    process.env.TARO_ENV = 'weapp'
    const { getCapturePlatformTips } = await import('@/adapters/media')
    expect(getCapturePlatformTips()).toEqual([])
  })
})
