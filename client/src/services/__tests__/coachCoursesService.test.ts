import { coachCoursesService } from '@/services/coachCoursesService'
import Taro from '@tarojs/taro'

const T = Taro as unknown as Record<string, jest.Mock>
const ok = (data: unknown) => ({
  statusCode: 200,
  data: { code: 0, message: '', data },
})

beforeEach(() => {
  ;(Taro as any).clearStorageSync()
  T.request.mockReset()
})

describe('coachCoursesService', () => {
  test('listMine → GET /users/me/coach/courses', async () => {
    T.request.mockResolvedValueOnce(ok([]))
    await coachCoursesService.listMine()
    expect(T.request.mock.calls[0][0].url).toMatch(/\/users\/me\/coach\/courses$/)
  })

  test('create → POST /users/me/coach/courses', async () => {
    T.request.mockResolvedValueOnce(ok({ id: 'crs_x', title: '课', stage: 1 }))
    await coachCoursesService.create({ title: '课', stage: 2 })
    const sent = T.request.mock.calls[0][0]
    expect(sent.method).toBe('POST')
    expect(sent.data).toEqual({ title: '课', stage: 2 })
  })

  test('publish → POST .../publish', async () => {
    T.request.mockResolvedValueOnce(ok({ id: 'crs_x', is_published: true }))
    await coachCoursesService.publish('crs_abc')
    expect(T.request.mock.calls[0][0].url).toMatch(
      /\/users\/me\/coach\/courses\/crs_abc\/publish$/,
    )
  })

  test('getDetail → GET .../{course_id}', async () => {
    T.request.mockResolvedValueOnce(ok({ course: { id: 'crs_x' }, lessons: [] }))
    await coachCoursesService.getDetail('crs_x')
    expect(T.request.mock.calls[0][0].url).toMatch(
      /\/users\/me\/coach\/courses\/crs_x$/,
    )
  })
})
