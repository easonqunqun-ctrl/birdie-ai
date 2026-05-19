/**
 * @jest-environment node
 *
 * analysisService.uploadToMinio 与 withUploadRetries 编排测试
 *
 * 上次 W9-C 把这部分留给"W10 RN smoke"，但 uploadFile 是分析链路最容易出错的
 * 那一公里（弱网 502 / 凭证过期 / 网关 404 / 同源回退 presigned 等），
 * 必须锁住关键不变式：
 *
 *  1. 默认走同源 `POST /v1/analyses/uploads/{id}/video`；不传 formData
 *  2. statusCode 200 + body.code=0 → resolve；其它 → reject 带状态码 + 截断 body
 *  3. statusCode 401 → "登录已过期" 且**不重试**（withUploadRetries 拒绝 401）
 *  4. statusCode 502/503/504 / `timeout` / `uploadFile:fail connect` → 重试
 *  5. statusCode 404 → 自动 fallback 走 presigned 直传（旧后端兼容）
 *  6. 同源上传 success.statusCode=200 但 body 非合法 JSON → "上传响应格式错误"，不重试
 *  7. `uploadLikelyNeedsFreshToken(msg)`：403 / Forbidden / AccessDenied / ExpiredSignature
 *     等都算"需要换凭证"，外层应重新调 getUploadToken（这里只验函数判定）
 *  8. onProgress 透传 progress / totalBytesSent / totalBytesExpectedToSend
 */

import type TaroType from '@tarojs/taro'

type AnalysisModule = typeof import('@/services/analysisService')
type Taro = typeof TaroType

interface LoadResult {
  analysisService: AnalysisModule['analysisService']
  uploadLikelyNeedsFreshToken: AnalysisModule['uploadLikelyNeedsFreshToken']
  Taro: Taro
}

async function loadModule(): Promise<LoadResult> {
  // resetModules 确保每个测试拿干净的 Taro / storage 实例（与 track.test.ts 同理）
  jest.resetModules()
  const Taro = (await import('@tarojs/taro')).default
  const mod = await import('@/services/analysisService')
  return { analysisService: mod.analysisService, uploadLikelyNeedsFreshToken: mod.uploadLikelyNeedsFreshToken, Taro }
}

const TOKEN = {
  upload_id: 'u-abc',
  upload_url: 'https://oss.example.com/bucket',
  fields: { key: 'video.mp4', policy: 'p' },
} as unknown as Parameters<AnalysisModule['analysisService']['uploadToMinio']>[1]

// helper：让 Taro.uploadFile 的 success 在下个 microtask 触发
function makeUploadFileMock(
  Taro: Taro,
  results: Array<{ statusCode: number; data?: string } | { errMsg: string }>,
  progressEvents: Array<{ progress: number; totalBytesSent: number; totalBytesExpectedToSend: number }> = [],
): jest.Mock {
  let i = 0
  const m = Taro.uploadFile as unknown as jest.Mock
  m.mockReset()
  m.mockImplementation((cfg) => {
    const result = results[i] ?? results[results.length - 1]
    i += 1
    const progressHandlers: Array<(e: typeof progressEvents[number]) => void> = []
    const task = {
      abort: jest.fn(),
      progress: (cb: (e: typeof progressEvents[number]) => void) => {
        progressHandlers.push(cb)
      },
    }
    queueMicrotask(() => {
      progressEvents.forEach((p) => progressHandlers.forEach((h) => h(p)))
      if ('statusCode' in result) {
        ;(cfg.success as (r: { statusCode: number; data: string }) => void)({
          statusCode: result.statusCode,
          data: result.data ?? '',
        })
      } else {
        ;(cfg.fail as (e: { errMsg: string }) => void)({ errMsg: result.errMsg })
      }
    })
    return task
  })
  return m
}

// withUploadRetries 内 backoff 是 `await sleepMs(...)` = `new Promise(setTimeout)`，
// 真实跑会让单测加好几秒。直接 stub setTimeout 在 0ms 内立刻 schedule，避免等待。
let originalSetTimeout: typeof setTimeout
beforeEach(() => {
  originalSetTimeout = global.setTimeout
  global.setTimeout = ((fn: (...args: unknown[]) => unknown) =>
    originalSetTimeout(fn, 0)) as unknown as typeof setTimeout
})
afterEach(() => {
  global.setTimeout = originalSetTimeout
})

// ============================================================================
// 纯函数 uploadLikelyNeedsFreshToken
// ============================================================================

describe('uploadLikelyNeedsFreshToken', () => {
  test('空消息 → false', async () => {
    const { uploadLikelyNeedsFreshToken } = await loadModule()
    expect(uploadLikelyNeedsFreshToken('')).toBe(false)
    expect(uploadLikelyNeedsFreshToken('   ')).toBe(false)
  })

  test.each([
    'HTTP 403 Forbidden',
    'Forbidden by policy',
    'AccessDenied',
    '<Error>ExpiredToken</Error>',
    'ExpiredSignature: please re-sign',
    'RequestExpired token expired',
    'The request signature we calculated does not match',
  ])('需要换凭证：%s', async (msg) => {
    const { uploadLikelyNeedsFreshToken } = await loadModule()
    expect(uploadLikelyNeedsFreshToken(msg)).toBe(true)
  })

  test.each([
    'HTTP 502 Bad Gateway',
    'uploadFile:fail timeout',
    '上传响应格式错误',
    '登录已过期，请重新登录',
  ])('不属于换凭证场景：%s', async (msg) => {
    const { uploadLikelyNeedsFreshToken } = await loadModule()
    expect(uploadLikelyNeedsFreshToken(msg)).toBe(false)
  })
})

// ============================================================================
// 同源 API 上传（默认路径）
// ============================================================================

describe('uploadToMinio · 同源 API 默认路径', () => {
  test('200 + body.code=0 → resolve，发往 /v1/analyses/uploads/{id}/video', async () => {
    const { analysisService, Taro } = await loadModule()
    makeUploadFileMock(Taro, [{ statusCode: 200, data: JSON.stringify({ code: 0 }) }])

    await analysisService.uploadToMinio('/tmp/clip.mp4', TOKEN)

    const cfg = (Taro.uploadFile as unknown as jest.Mock).mock.calls[0][0]
    expect(cfg.url).toBe('http://localhost:8000/v1/analyses/uploads/u-abc/video')
    expect(cfg.filePath).toBe('/tmp/clip.mp4')
    expect(cfg.name).toBe('file')
    // 同源走 multipart file，不带预签名 formData
    expect(cfg.formData).toBeUndefined()
  })

  test('200 + body.code != 0 → reject 带 body.message', async () => {
    const { analysisService, Taro } = await loadModule()
    makeUploadFileMock(Taro, [
      { statusCode: 200, data: JSON.stringify({ code: 50106, message: '配额不足' }) },
    ])
    await expect(analysisService.uploadToMinio('/x', TOKEN)).rejects.toThrow('配额不足')
  })

  test('200 + body 非 JSON → reject "上传响应格式错误"，不重试', async () => {
    const { analysisService, Taro } = await loadModule()
    const m = makeUploadFileMock(Taro, [{ statusCode: 200, data: '<html>oops</html>' }])
    await expect(analysisService.uploadToMinio('/x', TOKEN)).rejects.toThrow('上传响应格式错误')
    expect(m).toHaveBeenCalledTimes(1) // 不重试
  })

  test('401 → "登录已过期" 且不重试', async () => {
    const { analysisService, Taro } = await loadModule()
    const m = makeUploadFileMock(Taro, [{ statusCode: 401, data: '' }])
    await expect(analysisService.uploadToMinio('/x', TOKEN)).rejects.toThrow('登录已过期')
    expect(m).toHaveBeenCalledTimes(1)
  })

  test('502 → 重试 3 次后抛出最后一次错误', async () => {
    const { analysisService, Taro } = await loadModule()
    const m = makeUploadFileMock(Taro, [
      { statusCode: 502, data: '<title>502 Bad Gateway</title>' },
      { statusCode: 502, data: '<title>502 Bad Gateway</title>' },
      { statusCode: 502, data: '<title>502 Bad Gateway</title>' },
    ])
    await expect(analysisService.uploadToMinio('/x', TOKEN)).rejects.toThrow(/HTTP 502/)
    expect(m).toHaveBeenCalledTimes(3)
  })

  test('502 → 第 2 次成功 resolve', async () => {
    const { analysisService, Taro } = await loadModule()
    const m = makeUploadFileMock(Taro, [
      { statusCode: 502, data: '<title>502 Bad Gateway</title>' },
      { statusCode: 200, data: JSON.stringify({ code: 0 }) },
    ])
    await analysisService.uploadToMinio('/x', TOKEN)
    expect(m).toHaveBeenCalledTimes(2)
  })

  test('uploadFile:fail timeout → 触发重试', async () => {
    const { analysisService, Taro } = await loadModule()
    const m = makeUploadFileMock(Taro, [
      { errMsg: 'uploadFile:fail timeout' },
      { statusCode: 200, data: JSON.stringify({ code: 0 }) },
    ])
    await analysisService.uploadToMinio('/x', TOKEN)
    expect(m).toHaveBeenCalledTimes(2)
  })

  test('404 → 自动 fallback 到 presigned，使用 upload_url + fields formData', async () => {
    const { analysisService, Taro } = await loadModule()
    const m = makeUploadFileMock(Taro, [
      // 同源 attempt 1 返回 404
      { statusCode: 404, data: 'not found' },
      // 注意：withUploadRetries 不会重试 404（uploadNetworkLayerRetriable 排除 404）
      // 然后 uploadToMinio 自己的 catch 检测 404 → 进入 presigned
      // presigned attempt 1：204 / 200 都视为成功
      { statusCode: 204, data: '' },
    ])
    await analysisService.uploadToMinio('/x', TOKEN)
    expect(m).toHaveBeenCalledTimes(2)
    // 第二次是 presigned：URL 用 upload_url，formData 用 token.fields
    const cfg2 = (Taro.uploadFile as unknown as jest.Mock).mock.calls[1][0]
    expect(cfg2.url).toBe(TOKEN.upload_url)
    expect(cfg2.formData).toEqual(TOKEN.fields)
  })

  test('onProgress 透传 progress / totalBytesSent / totalBytesExpectedToSend', async () => {
    const { analysisService, Taro } = await loadModule()
    const progressFixtures = [
      { progress: 10, totalBytesSent: 100, totalBytesExpectedToSend: 1000 },
      { progress: 80, totalBytesSent: 800, totalBytesExpectedToSend: 1000 },
    ]
    makeUploadFileMock(
      Taro,
      [{ statusCode: 200, data: JSON.stringify({ code: 0 }) }],
      progressFixtures,
    )

    const recorded: number[] = []
    await analysisService.uploadToMinio('/x', TOKEN, {
      onProgress: (e) => recorded.push(e.progress),
    })
    expect(recorded).toEqual([10, 80])
  })

  test('Bearer Token 注入到同源上传 header（直传 presigned 不带）', async () => {
    const { analysisService, Taro } = await loadModule()
    const { storage } = await import('@/utils/storage')
    storage.setToken('upload-jwt')

    makeUploadFileMock(Taro, [{ statusCode: 200, data: JSON.stringify({ code: 0 }) }])
    await analysisService.uploadToMinio('/x', TOKEN)
    const cfg = (Taro.uploadFile as unknown as jest.Mock).mock.calls[0][0]
    expect(cfg.header.Authorization).toBe('Bearer upload-jwt')

    storage.clearAuthSession()
  })
})
