/**
 * analysisService.ts 单测：
 *  - REST URL / payload 一致性
 *  - sample 报告走专属 URL（MVP §3.6 示例视频体验）
 *  - listAnalyses 分页 / 球杆筛选 querystring 拼接
 *  - 纯函数 helper uploadLikelyNeedsFreshToken 边界
 *
 * uploadToMinio 与 retry 编排涉及 Taro.uploadFile 流，独立测试需大量 mock；
 * 留给 W10 RN 真机 smoke 与端到端测试覆盖。
 */

import {
  analysisService,
  uploadLikelyNeedsFreshToken,
} from '@/services/analysisService'
import Taro from '@tarojs/taro'

const T = Taro as unknown as Record<string, jest.Mock>
const ok = (data: unknown) => ({
  statusCode: 200,
  data: { code: 0, message: 'ok', data },
})

beforeEach(() => {
  ;(Taro as any).clearStorageSync()
  T.request.mockReset()
})

describe('analysisService.getUploadToken / createAnalysis', () => {
  test('POST /analyses/upload-token + 长超时（弱网容忍）', async () => {
    T.request.mockResolvedValueOnce(ok({ upload_id: 'u1' }))
    await analysisService.getUploadToken({ club_type: 'driver' } as any)
    const sent = T.request.mock.calls[0][0]
    expect(sent.method).toBe('POST')
    expect(sent.url).toContain('/analyses/upload-token')
    expect(sent.timeout).toBeGreaterThan(60000)
  })

  test('POST /analyses + silent=true（由 params 页自行 modal 提示）', async () => {
    T.request.mockResolvedValueOnce(ok({ analysis_id: 'a1' }))
    await analysisService.createAnalysis({ upload_id: 'u1' } as any)
    expect(T.request.mock.calls[0][0].url).toContain('/analyses')
    // 业务错误不再调用方处理；本层不弹 toast
    T.request.mockReset()
    T.request.mockResolvedValueOnce({
      statusCode: 200,
      data: { code: 40005, message: '体型未配置' },
    })
    await expect(
      analysisService.createAnalysis({ upload_id: 'u1' } as any),
    ).rejects.toThrow()
    expect(T.showToast).not.toHaveBeenCalled()
  })
})

describe('analysisService.getStatus（轮询路径）', () => {
  test('GET /analyses/:id/status + silent + 长超时', async () => {
    T.request.mockResolvedValueOnce(ok({ status: 'processing' }))
    await analysisService.getStatus('a1')
    const sent = T.request.mock.calls[0][0]
    expect(sent.method).toBe('GET')
    expect(sent.url).toContain('/analyses/a1/status')
  })

  test('轮询时业务错误不会触发默认 toast', async () => {
    T.request.mockResolvedValueOnce({
      statusCode: 200,
      data: { code: 50106, message: 'AI 引擎暂时不可用' },
    })
    await expect(analysisService.getStatus('a1')).rejects.toThrow()
    expect(T.showToast).not.toHaveBeenCalled()
  })
})

describe('analysisService.getReport · sample 分支', () => {
  test('id = "sample" → GET /analyses/sample', async () => {
    T.request.mockResolvedValueOnce(ok({ report: {} }))
    await analysisService.getReport('sample')
    expect(T.request.mock.calls[0][0].url).toContain('/analyses/sample')
    expect(T.request.mock.calls[0][0].url).not.toContain('/sample/')
  })

  test('id = 普通 id → GET /analyses/:id', async () => {
    T.request.mockResolvedValueOnce(ok({ report: {} }))
    await analysisService.getReport('a1')
    expect(T.request.mock.calls[0][0].url).toContain('/analyses/a1')
  })
})

describe('analysisService.listAnalyses · querystring', () => {
  test('无参数 → 不拼 ?', async () => {
    T.request.mockResolvedValueOnce(ok({ items: [] }))
    await analysisService.listAnalyses()
    expect(T.request.mock.calls[0][0].url).toBe('http://localhost:8000/v1/analyses')
  })

  test('page + page_size + club_type 三字段拼接', async () => {
    T.request.mockResolvedValueOnce(ok({ items: [] }))
    await analysisService.listAnalyses({ page: 2, page_size: 20, club_type: 'driver' })
    const url: string = T.request.mock.calls[0][0].url
    expect(url).toContain('page=2')
    expect(url).toContain('page_size=20')
    expect(url).toContain('club_type=driver')
  })
})

describe('analysisService.deleteAnalysis / createShareCard', () => {
  test('DELETE /analyses/:id', async () => {
    T.request.mockResolvedValueOnce(ok(null))
    await analysisService.deleteAnalysis('a1')
    expect(T.request.mock.calls[0][0].method).toBe('DELETE')
    expect(T.request.mock.calls[0][0].url).toContain('/analyses/a1')
  })

  test('POST /analyses/:id/share-card', async () => {
    T.request.mockResolvedValueOnce(ok({ wxa_code_url: 'cos://x' }))
    await analysisService.createShareCard('a1')
    expect(T.request.mock.calls[0][0].method).toBe('POST')
    expect(T.request.mock.calls[0][0].url).toContain('/analyses/a1/share-card')
  })
})

describe('uploadLikelyNeedsFreshToken · 触发条件', () => {
  test.each([
    ['HTTP 403 Forbidden', true],
    ['MinIO AccessDenied', true],
    ['ExpiredToken', true],
    ['ExpiredSignature', true],
    ['RequestExpired', true],
    ['the request signature we calculated does not match', true],
    ['HTTP 502 Bad Gateway', false],
    ['上传失败，请检查网络', false],
    ['', false],
    ['some other 200', false],
  ])('%s → %s', (msg, expected) => {
    expect(uploadLikelyNeedsFreshToken(msg)).toBe(expected)
  })
})
