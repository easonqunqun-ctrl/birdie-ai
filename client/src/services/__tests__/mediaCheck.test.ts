/**
 * @jest-environment node
 *
 * mediaCheck.checkVideoFirstFrame：首帧合规预检（Taro.uploadFile + fail-open）
 */

import type TaroType from '@tarojs/taro'

type Taro = typeof TaroType

interface LoadResult {
  checkVideoFirstFrame: typeof import('@/services/mediaCheck').checkVideoFirstFrame
  Taro: Taro
}

async function loadModule(): Promise<LoadResult> {
  jest.resetModules()
  const Taro = (await import('@tarojs/taro')).default
  const { checkVideoFirstFrame } = await import('@/services/mediaCheck')
  return { checkVideoFirstFrame, Taro }
}

function mockUpload(
  Taro: Taro,
  impl: (cfg: {
    url: string
    filePath: string
    name: string
    formData?: Record<string, string>
    header?: Record<string, string>
    success?: (res: { statusCode: number; data: string }) => void
    fail?: (err: { errMsg: string }) => void
  }) => void,
) {
  ;(Taro.uploadFile as jest.Mock).mockImplementation(impl)
}

beforeEach(() => {
  jest.resetModules()
})

describe('checkVideoFirstFrame', () => {
  test('空路径 → 直接放行', async () => {
    const { checkVideoFirstFrame, Taro } = await loadModule()
    const r = await checkVideoFirstFrame('')
    expect(r).toEqual({ passed: true })
    expect(Taro.uploadFile).not.toHaveBeenCalled()
  })

  test('成功 code=0 → 返回后端 data', async () => {
    const { checkVideoFirstFrame, Taro } = await loadModule()
    mockUpload(Taro, (cfg) => {
      cfg.success?.({
        statusCode: 200,
        data: JSON.stringify({ code: 0, message: 'ok', data: { passed: false, reason: '违规' } }),
      })
    })
    const r = await checkVideoFirstFrame('/tmp/thumb.jpg', 'share')
    expect(r).toEqual({ passed: false, reason: '违规' })
    const sent = (Taro.uploadFile as jest.Mock).mock.calls[0][0]
    expect(sent.url).toContain('/security/media-check')
    expect(sent.filePath).toBe('/tmp/thumb.jpg')
    expect(sent.formData).toEqual({ scene: 'share' })
  })

  test('5xx → fail-open passed=true', async () => {
    const { checkVideoFirstFrame, Taro } = await loadModule()
    mockUpload(Taro, (cfg) => {
      cfg.success?.({ statusCode: 503, data: 'busy' })
    })
    const r = await checkVideoFirstFrame('/t.jpg')
    expect(r.passed).toBe(true)
    expect(r.reason).toMatch(/不可用/)
  })

  test('4xx 业务码 → fail-open', async () => {
    const { checkVideoFirstFrame, Taro } = await loadModule()
    mockUpload(Taro, (cfg) => {
      cfg.success?.({
        statusCode: 200,
        data: JSON.stringify({ code: 413, message: '图片过大' }),
      })
    })
    const r = await checkVideoFirstFrame('/t.jpg')
    expect(r.passed).toBe(true)
    expect(r.reason).toBe('图片过大')
  })

  test('非 JSON 响应 → fail-open', async () => {
    const { checkVideoFirstFrame, Taro } = await loadModule()
    mockUpload(Taro, (cfg) => {
      cfg.success?.({ statusCode: 200, data: 'not-json' })
    })
    const r = await checkVideoFirstFrame('/t.jpg')
    expect(r.passed).toBe(true)
    expect(r.reason).toMatch(/解析/)
  })

  test('uploadFile fail → fail-open', async () => {
    const { checkVideoFirstFrame, Taro } = await loadModule()
    mockUpload(Taro, (cfg) => {
      cfg.fail?.({ errMsg: 'uploadFile:fail' })
    })
    const r = await checkVideoFirstFrame('/t.jpg')
    expect(r.passed).toBe(true)
    expect(r.reason).toMatch(/网络/)
  })

  test('有 token 时注入 Bearer', async () => {
    const { checkVideoFirstFrame, Taro } = await loadModule()
    const storage = await import('@/utils/storage')
    storage.storage.setToken('tok-1')
    mockUpload(Taro, (cfg) => {
      expect(cfg.header?.Authorization).toBe('Bearer tok-1')
      cfg.success?.({
        statusCode: 200,
        data: JSON.stringify({ code: 0, message: 'ok', data: { passed: true } }),
      })
    })
    await checkVideoFirstFrame('/t.jpg')
  })
})
