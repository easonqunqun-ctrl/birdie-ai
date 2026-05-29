/**
 * coachRecapService.ts 单测
 */

import Taro from '@tarojs/taro'
import { coachRecapService } from '@/services/coachRecapService'

const T = Taro as unknown as { request: jest.Mock }

function ok<T>(data: T) {
  return { statusCode: 200, data: { code: 0, data } }
}

beforeEach(() => {
  T.request.mockReset()
})

describe('coachRecapService', () => {
  test('create → POST /coach/sessions/recap', async () => {
    T.request.mockResolvedValueOnce(ok({ recap_id: 'csr_1', ai_summary: 'x', status: 'finalized' }))
    await coachRecapService.create({
      session_date: '2026-05-29',
      student_ids: ['usr_s'],
      analysis_ids: ['ana_1'],
    })
    const sent = T.request.mock.calls[0][0]
    expect(sent.method).toBe('POST')
    expect(sent.url).toMatch(/\/coach\/sessions\/recap$/)
  })

  test('exportPdf → POST /coach/sessions/{id}/export-pdf', async () => {
    T.request.mockResolvedValueOnce(
      ok({ pdf_url: 'https://x/a.pdf', pdf_url_expires_at: '2026-05-30T00:00:00Z' }),
    )
    await coachRecapService.exportPdf('csr_1')
    const sent = T.request.mock.calls[0][0]
    expect(sent.method).toBe('POST')
    expect(sent.url).toMatch(/\/coach\/sessions\/csr_1\/export-pdf$/)
  })

  test('list → GET /coach/sessions/recaps', async () => {
    T.request.mockResolvedValueOnce(ok({ items: [], total: 0 }))
    await coachRecapService.list(2, 10)
    const sent = T.request.mock.calls[0][0]
    expect(sent.method).toBe('GET')
    expect(sent.url).toMatch(/\/coach\/sessions\/recaps\?page=2&page_size=10$/)
  })
})
