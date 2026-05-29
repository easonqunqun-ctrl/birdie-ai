import { coachTaskService } from '@/services/coachTaskService'
import Taro from '@tarojs/taro'

const T = Taro as unknown as Record<string, jest.Mock>

beforeEach(() => {
  T.request.mockReset()
})

describe('coachTaskService', () => {
  test('assign → POST /coach/tasks/assign', async () => {
    T.request.mockResolvedValueOnce({
      statusCode: 200,
      data: { code: 0, data: { id: 'ctask_1' } },
    })
    await coachTaskService.assign({
      student_user_id: 'usr_s',
      source_type: 'drill',
      drill_id: 'drill_half_swing',
      target_week: '2026-05-26',
      target_count: 3,
      coach_note: '重点练',
    })
    const sent = T.request.mock.calls[0][0]
    expect(sent.method).toBe('POST')
    expect(sent.url).toMatch(/\/coach\/tasks\/assign$/)
    expect(sent.data.target_count).toBe(3)
  })

  test('list → GET /coach/tasks', async () => {
    T.request.mockResolvedValueOnce({
      statusCode: 200,
      data: { code: 0, data: { items: [], total: 0 } },
    })
    await coachTaskService.list({ studentId: 'usr_s', status: 'assigned' })
    const sent = T.request.mock.calls[0][0]
    expect(sent.method).toBe('GET')
    expect(sent.url).toMatch(/\/coach\/tasks\?student_id=usr_s&status=assigned$/)
  })
})
