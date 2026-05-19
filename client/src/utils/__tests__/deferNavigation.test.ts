import Taro from '@tarojs/taro'
import { deferReLaunch } from '@/utils/deferNavigation'

const T = Taro as unknown as Record<string, jest.Mock>

beforeEach(() => {
  jest.useFakeTimers()
  T.reLaunch.mockReset()
})

afterEach(() => {
  jest.useRealTimers()
  delete (Taro as unknown as { nextTick?: unknown }).nextTick
})

describe('deferReLaunch', () => {
  test('有 nextTick 时先 nextTick 再延迟 reLaunch', () => {
    const nextTick = jest.fn((cb: () => void) => cb())
    ;(Taro as unknown as { nextTick: typeof nextTick }).nextTick = nextTick

    deferReLaunch('/pages/index/index')
    expect(T.reLaunch).not.toHaveBeenCalled()

    jest.runAllTimers()
    expect(nextTick).toHaveBeenCalled()
    expect(T.reLaunch).toHaveBeenCalledWith({ url: '/pages/index/index' })
  })

  test('无 nextTick 时直接 setTimeout', () => {
    deferReLaunch('/pages/login/index')
    expect(T.reLaunch).not.toHaveBeenCalled()
    jest.runAllTimers()
    expect(T.reLaunch).toHaveBeenCalledWith({ url: '/pages/login/index' })
  })
})
