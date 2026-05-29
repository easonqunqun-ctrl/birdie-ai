import { proFavoritesService } from '@/services/proFavoritesService'
import Taro from '@tarojs/taro'

const T = Taro as unknown as Record<string, jest.Mock>

beforeEach(() => {
  T.request.mockReset()
})

describe('proFavoritesService', () => {
  test('list → GET /users/me/pros/favorites', async () => {
    T.request.mockResolvedValueOnce({ statusCode: 200, data: { code: 0, data: [] } })
    await proFavoritesService.list()
    const sent = T.request.mock.calls[0][0]
    expect(sent.method).toBe('GET')
    expect(sent.url).toMatch(/\/users\/me\/pros\/favorites$/)
  })

  test('add → POST /users/me/pros/favorites', async () => {
    T.request.mockResolvedValueOnce({
      statusCode: 200,
      data: { code: 0, data: { clip_id: 'psc_1' } },
    })
    await proFavoritesService.add({ clip_id: 'psc_1' })
    const sent = T.request.mock.calls[0][0]
    expect(sent.method).toBe('POST')
    expect(sent.url).toMatch(/\/users\/me\/pros\/favorites$/)
    expect(sent.data).toEqual({ clip_id: 'psc_1' })
  })

  test('tryIt → POST /users/me/pros/favorites/{clip_id}/try-it', async () => {
    T.request.mockResolvedValueOnce({
      statusCode: 200,
      data: { code: 0, data: { training_task_id: 'task_1', created: true } },
    })
    await proFavoritesService.tryIt('psc_1')
    const sent = T.request.mock.calls[0][0]
    expect(sent.method).toBe('POST')
    expect(sent.url).toMatch(/\/users\/me\/pros\/favorites\/psc_1\/try-it$/)
  })
})
