describe('share adapter', () => {
  const origTaroEnv = process.env.TARO_ENV

  afterEach(() => {
    process.env.TARO_ENV = origTaroEnv
    jest.resetModules()
  })

  test('weapp 导出可调用的分享钩子', () => {
    process.env.TARO_ENV = 'weapp'
    jest.resetModules()
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const { useShareAppMessage, useShareTimeline } = require('../share')
    expect(typeof useShareAppMessage).toBe('function')
    expect(typeof useShareTimeline).toBe('function')
  })

  test('rn 为 no-op 且可安全调用', () => {
    process.env.TARO_ENV = 'rn'
    jest.resetModules()
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const { useShareAppMessage, useShareTimeline } = require('../share')
    expect(() => useShareAppMessage(() => ({ title: 'x' }))).not.toThrow()
    expect(() => useShareTimeline(() => ({ title: 'x' }))).not.toThrow()
  })
})
