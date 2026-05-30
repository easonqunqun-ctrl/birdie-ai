/**
 * P2-M12-03 · prosService 客户端单测：URL / method / 过滤参数。
 */

import { prosService } from '@/services/prosService'
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

describe('prosService', () => {
  test('list → GET /pros', async () => {
    T.request.mockResolvedValueOnce(ok([]))
    await prosService.list()
    const sent = T.request.mock.calls[0][0]
    expect(sent.method).toBe('GET')
    expect(sent.url).toMatch(/\/pros$/)
  })

  test('detail → GET /pros/{id}', async () => {
    T.request.mockResolvedValueOnce(
      ok({
        id: 'pp_abc',
        name: '示范',
        name_en: 'Demo',
        nationality: 'CHN',
        handedness: 'right',
        height_cm: 180,
        avatar_url: null,
        short_bio: null,
        license_status: 'public_clip',
        is_active: true,
        sort_order: 0,
      }),
    )
    const res = await prosService.detail('pp_abc')
    expect(res.name).toBe('示范')
    expect(T.request.mock.calls[0][0].url).toMatch(/\/pros\/pp_abc$/)
  })

  test('clips without filter → GET /pros/{id}/clips', async () => {
    T.request.mockResolvedValueOnce(ok([]))
    await prosService.clips('pp_x')
    expect(T.request.mock.calls[0][0].url).toMatch(/\/pros\/pp_x\/clips$/)
  })

  test('clips with camera_angle → query string', async () => {
    T.request.mockResolvedValueOnce(ok([]))
    await prosService.clips('pp_x', { camera_angle: 'face_on' })
    expect(T.request.mock.calls[0][0].url).toContain('camera_angle=face_on')
  })

  test('clips with both filters → combined query', async () => {
    T.request.mockResolvedValueOnce(ok([]))
    await prosService.clips('pp_x', {
      camera_angle: 'down_the_line',
      club_type: 'iron_7',
    })
    const url: string = T.request.mock.calls[0][0].url
    expect(url).toContain('camera_angle=down_the_line')
    expect(url).toContain('club_type=iron_7')
  })

  test('club_type with special chars → encodeURIComponent', async () => {
    T.request.mockResolvedValueOnce(ok([]))
    await prosService.clips('pp_x', { club_type: 'iron 7' })
    expect(T.request.mock.calls[0][0].url).toContain('club_type=iron%207')
  })

  test('matchForAnalysis → GET /analyses/{id}/pro-matches', async () => {
    T.request.mockResolvedValueOnce(
      ok({
        analysis_id: 'ana_abc',
        matches: [],
        recorded_match_id: null,
      }),
    )
    await prosService.matchForAnalysis('ana_abc')
    const sent = T.request.mock.calls[0][0]
    expect(sent.method).toBe('GET')
    expect(sent.url).toMatch(/\/analyses\/ana_abc\/pro-matches$/)
    expect(sent.silent).toBe(true)
  })

  test('matchForAnalysis with limit and record=false → query string', async () => {
    T.request.mockResolvedValueOnce(
      ok({
        analysis_id: 'ana_x',
        matches: [],
        recorded_match_id: null,
      }),
    )
    await prosService.matchForAnalysis('ana_x', { limit: 3, record: false })
    const url: string = T.request.mock.calls[0][0].url
    expect(url).toContain('limit=3')
    expect(url).toContain('record=false')
  })

  test('currentTopic → GET /pros/topics/current', async () => {
    T.request.mockResolvedValueOnce(
      ok({
        id: 'pt_abc',
        code: 'demo_weekly',
        title: '本周精选',
        subtitle: '副标题',
        banner_url: null,
        summary: '摘要',
        clip_ids: ['psc_1'],
        week_starts_at: '2026-05-26',
        published_at: '2026-05-26T00:00:00Z',
        clips: [],
      }),
    )
    const res = await prosService.currentTopic()
    expect(res?.title).toBe('本周精选')
    expect(T.request.mock.calls[0][0].url).toMatch(/\/pros\/topics\/current$/)
  })

  test('annotations → GET /pros/clips/{id}/annotations', async () => {
    T.request.mockResolvedValueOnce(
      ok([
        {
          id: 'pca_1',
          clip_id: 'psc_1',
          annotation_type: 'text',
          content: '上杆顶点',
          time_marker_ms: 1200,
          is_visible: true,
          created_at: '2026-05-29T00:00:00Z',
        },
      ]),
    )
    const res = await prosService.annotations('psc_1')
    expect(res[0].content).toBe('上杆顶点')
    expect(T.request.mock.calls[0][0].method).toBe('GET')
    expect(T.request.mock.calls[0][0].url).toMatch(/\/pros\/clips\/psc_1\/annotations$/)
  })

  test('pgcInsight → POST /pros/clips/{id}/pgc-insight with analysis_id', async () => {
    T.request.mockResolvedValueOnce(
      ok({
        clip_id: 'psc_1',
        insight: '保持脊柱角',
      }),
    )
    const res = await prosService.pgcInsight('psc_1', { analysis_id: 'ana_x' })
    expect(res.insight).toBe('保持脊柱角')
    const sent = T.request.mock.calls[0][0]
    expect(sent.method).toBe('POST')
    expect(sent.url).toMatch(/\/pros\/clips\/psc_1\/pgc-insight$/)
    expect(sent.data).toEqual({ analysis_id: 'ana_x' })
  })
})
