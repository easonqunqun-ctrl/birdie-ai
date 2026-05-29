/**
 * coachStudentsService.ts 单测
 */

import Taro from '@tarojs/taro'
import { coachStudentsService } from '@/services/coachStudentsService'

const T = Taro as unknown as { request: jest.Mock }

function ok<T>(data: T) {
  return { statusCode: 200, data: { code: 0, data } }
}

beforeEach(() => {
  T.request.mockReset()
})

describe('coachStudentsService.invite / myCoachOverview', () => {
  test('invite → POST /coach/students/invite', async () => {
    T.request.mockResolvedValueOnce(ok({ id: 'csr_1', status: 'pending' }))
    await coachStudentsService.invite({ student_user_id: 'usr_s', message: 'hi' })
    const sent = T.request.mock.calls[0][0]
    expect(sent.method).toBe('POST')
    expect(sent.url).toContain('/coach/students/invite')
    expect(sent.data).toEqual({ student_user_id: 'usr_s', message: 'hi' })
  })

  test('myCoachOverview → GET /users/me/coach', async () => {
    T.request.mockResolvedValueOnce(ok({ pending: [], active: null, paused: null }))
    await coachStudentsService.myCoachOverview()
    const sent = T.request.mock.calls[0][0]
    expect(sent.method).toBe('GET')
    expect(sent.url).toContain('/users/me/coach')
  })

  test('list → GET /coach/students', async () => {
    T.request.mockResolvedValueOnce(ok({ items: [], total: 0 }))
    await coachStudentsService.list('active')
    const sent = T.request.mock.calls[0][0]
    expect(sent.method).toBe('GET')
    expect(sent.url).toContain('/coach/students?status=active')
  })

  test('updateVisibility → PUT /users/me/coach/{id}/visibility', async () => {
    T.request.mockResolvedValueOnce(ok({ id: 'csr_1', status: 'active' }))
    await coachStudentsService.updateVisibility('csr_1', { handicap: true })
    const sent = T.request.mock.calls[0][0]
    expect(sent.method).toBe('PUT')
    expect(sent.url).toContain('/users/me/coach/csr_1/visibility')
    expect(sent.data).toEqual({ handicap: true })
  })
})
