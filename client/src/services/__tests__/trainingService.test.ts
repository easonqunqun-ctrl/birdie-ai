/**
 * trainingService 单测：训练计划 / 打卡 / 从分析加入计划
 */

import { trainingService } from '@/services/trainingService'
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

describe('trainingService', () => {
  test('getCurrentPlan → GET /users/me/training-plan/current', async () => {
    T.request.mockResolvedValueOnce(ok(null))
    await trainingService.getCurrentPlan()
    const sent = T.request.mock.calls[0][0]
    expect(sent.method).toBe('GET')
    expect(sent.url).toContain('/users/me/training-plan/current')
  })

  test('completeTask → POST /training-plan/tasks/:id/complete', async () => {
    T.request.mockResolvedValueOnce(ok({ current_streak_days: 3 }))
    await trainingService.completeTask('task-1', { notes: 'ok' })
    const sent = T.request.mock.calls[0][0]
    expect(sent.method).toBe('POST')
    expect(sent.url).toContain('/training-plan/tasks/task-1/complete')
    expect(sent.data).toEqual({ notes: 'ok' })
  })

  test('addToPlanFromAnalysis → POST；业务错误不 toast（silent）', async () => {
    T.request.mockResolvedValueOnce(ok({ id: 'plan-1' }))
    await trainingService.addToPlanFromAnalysis('analysis-9')
    const sent = T.request.mock.calls[0][0]
    expect(sent.method).toBe('POST')
    expect(sent.url).toContain('/training-plan/from-analysis/analysis-9')

    T.request.mockReset()
    T.request.mockResolvedValueOnce({
      statusCode: 200,
      data: { code: 40015, message: '无 issue' },
    })
    await expect(trainingService.addToPlanFromAnalysis('bad')).rejects.toThrow()
    expect(T.showToast).not.toHaveBeenCalled()
  })

  test('listPracticeLogs → GET with month query', async () => {
    T.request.mockResolvedValueOnce(ok([]))
    await trainingService.listPracticeLogs('2026-05')
    const sent = T.request.mock.calls[0][0]
    expect(sent.method).toBe('GET')
    expect(sent.url).toContain('/users/me/practice-logs?month=2026-05')
  })
})
