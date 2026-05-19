/**
 * track 单测
 *
 * 重点：track.ts 有模块级 mutable state（queue / timer / retryCount / flushing），
 * 每个测试必须 jest.resetModules() 重新拉取干净的模块实例。
 *
 * TRACK_DISABLED 在模块加载时计算（IIFE 读 APP_ENV），所以切环境也得在
 * resetModules 之后改 globalThis.APP_ENV，然后再 await import('@/utils/track')。
 *
 * 不变式：
 *  - APP_ENV === 'test' 全程禁用（不入队、不发请求）
 *  - error_report 立即 flush，不等 5s 定时器
 *  - 队列 >= MAX_BATCH_SIZE (20) 立即 flush
 *  - 普通事件入队后 5s 内定时 flush（这里改用 jest fake timer 加速）
 *  - flush 失败 → batch 塞回队头 + retry；3 次后丢弃 + console.warn
 *  - trackError 提取 message + 截断 stack 到 2KB
 */

import type TaroType from '@tarojs/taro'

type TrackModule = typeof import('@/utils/track')
type StorageModule = typeof import('@/utils/storage')
type TaroDefault = typeof TaroType

interface LoadResult extends TrackModule {
  /** track.ts 内部实际使用的 Taro 实例（resetModules 后会换一个 jest.fn 引用，
   *  必须从 helper 里拿出来，否则 mock 配置作用在错的实例上） */
  Taro: TaroDefault
  /** track.ts 通过 import 拿到的 storage 实例（同样 resetModules 后会换） */
  storage: StorageModule['storage']
}

async function loadTrack(env: 'production' | 'test' = 'production'): Promise<LoadResult> {
  ;(globalThis as unknown as { APP_ENV: string }).APP_ENV = env
  jest.resetModules()
  const Taro = (await import('@tarojs/taro')).default
  const { storage } = await import('@/utils/storage')
  const track = await import('@/utils/track')
  ;(Taro.request as jest.Mock).mockResolvedValue({ statusCode: 200, data: {} })
  return Object.assign({ Taro, storage }, track)
}

beforeEach(() => {
  jest.useFakeTimers()
})

afterEach(() => {
  jest.useRealTimers()
})

describe('track · APP_ENV=test 时全程禁用', () => {
  test('test 环境下 track() / flushTrack() 都不发请求', async () => {
    const { track, flushTrack, Taro } = await loadTrack('test')
    track('page_view', { path: '/x' })
    track('error_report', { msg: 'oops' })
    await flushTrack()
    expect(Taro.request).not.toHaveBeenCalled()
  })
})

describe('track · 入队与触发 flush', () => {
  test('普通事件入队后不立刻发，5s 定时器到点再发', async () => {
    const { track, Taro } = await loadTrack('production')
    track('page_view', { path: '/a' })

    expect(Taro.request).not.toHaveBeenCalled()
    await jest.advanceTimersByTimeAsync(5000)
    expect(Taro.request).toHaveBeenCalledTimes(1)
    const cfg = (Taro.request as jest.Mock).mock.calls[0][0]
    expect(cfg.url).toBe('http://localhost:8000/v1/events')
    expect(cfg.method).toBe('POST')
    expect(cfg.data.events).toHaveLength(1)
    expect(cfg.data.events[0]).toMatchObject({ name: 'page_view', payload: { path: '/a' } })
    expect(typeof cfg.data.events[0].client_ts).toBe('number')
  })

  test('error_report 立即 flush，不等 5s', async () => {
    const { track, Taro } = await loadTrack('production')
    track('error_report', { msg: 'oops' })

    // 立即 flush 是 microtask 走的；advance 0ms 把 microtask 跑光
    await jest.advanceTimersByTimeAsync(0)
    expect(Taro.request).toHaveBeenCalledTimes(1)
    const ev = (Taro.request as jest.Mock).mock.calls[0][0].data.events[0]
    expect(ev.name).toBe('error_report')
  })

  test('队列长度 >= 20 立即 flush', async () => {
    const { track, Taro } = await loadTrack('production')
    for (let i = 0; i < 19; i += 1) track('page_view', { i })
    expect(Taro.request).not.toHaveBeenCalled()
    track('page_view', { i: 19 })
    await jest.advanceTimersByTimeAsync(0)
    expect(Taro.request).toHaveBeenCalledTimes(1)
    expect((Taro.request as jest.Mock).mock.calls[0][0].data.events).toHaveLength(20)
  })

  test('显式 flushTrack 主动发出当前批次', async () => {
    const { track, flushTrack, Taro } = await loadTrack('production')
    track('page_view', { path: '/a' })
    track('page_view', { path: '/b' })
    await flushTrack()
    expect(Taro.request).toHaveBeenCalledTimes(1)
    expect((Taro.request as jest.Mock).mock.calls[0][0].data.events).toHaveLength(2)
  })
})

describe('track · 鉴权头', () => {
  test('有 token 时携带 Bearer Authorization', async () => {
    const { track, flushTrack, Taro, storage } = await loadTrack('production')
    storage.setToken('test-jwt-token')
    track('page_view')
    await flushTrack()

    const cfg = (Taro.request as jest.Mock).mock.calls[0][0]
    expect(cfg.header.Authorization).toBe('Bearer test-jwt-token')
  })

  test('无 token 时不带 Authorization（埋点端点允许匿名 W8-T5）', async () => {
    const { track, flushTrack, Taro } = await loadTrack('production')
    track('page_view')
    await flushTrack()

    const cfg = (Taro.request as jest.Mock).mock.calls[0][0]
    expect(cfg.header.Authorization).toBeUndefined()
  })
})

describe('track · 失败重试', () => {
  test('5xx 失败 → 塞回队头 + scheduleFlush；下次定时器到点重试', async () => {
    const { track, flushTrack, Taro } = await loadTrack('production')
    ;(Taro.request as jest.Mock)
      .mockReset()
      .mockResolvedValueOnce({ statusCode: 500, data: {} })
      .mockResolvedValueOnce({ statusCode: 200, data: {} })

    track('page_view', { i: 0 })
    await flushTrack()
    expect(Taro.request).toHaveBeenCalledTimes(1)

    await jest.advanceTimersByTimeAsync(5000)
    expect(Taro.request).toHaveBeenCalledTimes(2)
  })

  test('网络异常（reject）连续 3 次后丢弃这批并 console.warn', async () => {
    const warnSpy = jest.spyOn(console, 'warn').mockImplementation(() => undefined)
    const { track, flushTrack, Taro } = await loadTrack('production')
    ;(Taro.request as jest.Mock).mockReset().mockRejectedValue(
      Object.assign(new Error('timeout'), { errMsg: 'request:fail timeout' }),
    )

    track('page_view', { i: 0 })
    await flushTrack()
    await jest.advanceTimersByTimeAsync(5000)
    await jest.advanceTimersByTimeAsync(5000)

    expect(Taro.request).toHaveBeenCalledTimes(3)
    const warnCalls = warnSpy.mock.calls.map((c) => String(c[0]))
    expect(warnCalls.some((s) => s.includes('[track] drop batch after retries'))).toBe(true)

    warnSpy.mockRestore()
  })
})

describe('trackError', () => {
  test('Error 对象 → 提取 message + stack；非 Error → String(err)', async () => {
    const { trackError, flushTrack, Taro } = await loadTrack('production')

    trackError(new Error('boom-1'), { where: 'unit' })
    await flushTrack()
    const ev1 = (Taro.request as jest.Mock).mock.calls[0][0].data.events[0]
    expect(ev1.name).toBe('error_report')
    expect(ev1.payload).toMatchObject({ where: 'unit', message: 'boom-1' })
    expect(typeof ev1.payload.stack).toBe('string')

    ;(Taro.request as jest.Mock).mockClear()
    trackError('plain-string-error')
    await flushTrack()
    const ev2 = (Taro.request as jest.Mock).mock.calls[0][0].data.events[0]
    expect(ev2.payload.message).toBe('plain-string-error')
    expect(ev2.payload.stack).toBeUndefined()
  })

  test('stack 超 2KB 时被截断到 2048', async () => {
    const { trackError, flushTrack, Taro } = await loadTrack('production')

    const err = new Error('long')
    err.stack = 'x'.repeat(5000)
    trackError(err)
    await flushTrack()

    const ev = (Taro.request as jest.Mock).mock.calls[0][0].data.events[0]
    expect((ev.payload.stack as string).length).toBe(2048)
  })
})
