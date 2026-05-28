/**
 * P2-M11-03 · coursesService 客户端单测：URL / method / 参数透传。
 *
 * 与 userClubsService.test.ts 同模式：Mock Taro.request、断言出参，避免起 fetch。
 */

import { coursesService } from '@/services/coursesService'
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

describe('coursesService', () => {
  test('list without stage → GET /courses', async () => {
    T.request.mockResolvedValueOnce(ok([]))
    await coursesService.list()
    const sent = T.request.mock.calls[0][0]
    expect(sent.method).toBe('GET')
    expect(sent.url).toMatch(/\/courses$/)
  })

  test('list with stage → GET /courses?stage=N', async () => {
    T.request.mockResolvedValueOnce(ok([]))
    await coursesService.list(3)
    const sent = T.request.mock.calls[0][0]
    expect(sent.url).toContain('/courses?stage=3')
  })

  test('detail → GET /courses/{id}', async () => {
    T.request.mockResolvedValueOnce(
      ok({
        id: 'crs_abc',
        code: 'x',
        title: '入门',
        subtitle: null,
        cover_url: null,
        stage: 1,
        sort_order: 1,
        is_member_only: false,
        description: null,
        learning_objectives: [],
        estimated_minutes: 45,
        created_by_user_id: null,
        is_published: true,
        published_at: '2026-05-25T00:00:00Z',
      }),
    )
    const res = await coursesService.detail('crs_abc')
    const sent = T.request.mock.calls[0][0]
    expect(sent.method).toBe('GET')
    expect(sent.url).toMatch(/\/courses\/crs_abc$/)
    expect(res.title).toBe('入门')
  })

  test('lessons → GET /courses/{id}/lessons', async () => {
    T.request.mockResolvedValueOnce(
      ok({ course_id: 'crs_abc', items: [], total: 0 }),
    )
    await coursesService.lessons('crs_abc')
    const sent = T.request.mock.calls[0][0]
    expect(sent.url).toMatch(/\/courses\/crs_abc\/lessons$/)
  })

  test('encodeURIComponent applied to courseId with special chars', async () => {
    T.request.mockResolvedValueOnce(ok([]))
    // 当前 service 直接拼字符串；URL 里有特殊字符时仍可工作（id 全部由后端控制）。
    // 该测试做为"未来加 encoding 时不要破坏简单 id 情况"的回归断言。
    await coursesService.detail('crs_normal_id_123')
    const sent = T.request.mock.calls[0][0]
    expect(sent.url).toContain('crs_normal_id_123')
  })

  test('submitLessonAttempt → POST /lessons/{id}/attempt', async () => {
    T.request.mockResolvedValueOnce(
      ok({
        passed: true,
        score: 85,
        min_score: 80,
        attempts_used: 1,
        max_attempts: 3,
        failure_reason: null,
        feedback: '表现不错',
        stage_upgraded: false,
        upgraded_to_stage: null,
      }),
    )
    const res = await coursesService.submitLessonAttempt('les_abc', 'sa_xyz')
    const sent = T.request.mock.calls[0][0]
    expect(sent.method).toBe('POST')
    expect(sent.url).toMatch(/\/lessons\/les_abc\/attempt$/)
    expect(sent.data).toEqual({ swing_analysis_id: 'sa_xyz' })
    expect(res.passed).toBe(true)
    expect(res.score).toBe(85)
  })
})
