import { coachAnnotationService } from '@/services/coachAnnotationService'
import Taro from '@tarojs/taro'

const T = Taro as unknown as Record<string, jest.Mock>

beforeEach(() => {
  T.request.mockReset()
})

describe('coachAnnotationService', () => {
  test('listForAnalysis → GET /analyses/{id}/coach-annotations', async () => {
    T.request.mockResolvedValueOnce({ statusCode: 200, data: { code: 0, data: [] } })
    await coachAnnotationService.listForAnalysis('ana_x')
    const sent = T.request.mock.calls[0][0]
    expect(sent.method).toBe('GET')
    expect(sent.url).toMatch(/\/analyses\/ana_x\/coach-annotations$/)
  })

  test('createVideoRef → POST /coach/analyses/{id}/annotations', async () => {
    T.request.mockResolvedValueOnce({
      statusCode: 200,
      data: { code: 0, data: { id: 'can_1', pro_clip_id: 'psc_1' } },
    })
    await coachAnnotationService.createVideoRef('ana_x', { pro_clip_id: 'psc_1' })
    const sent = T.request.mock.calls[0][0]
    expect(sent.method).toBe('POST')
    expect(sent.url).toMatch(/\/coach\/analyses\/ana_x\/annotations$/)
    expect(sent.data).toEqual({
      annotation_type: 'video_ref',
      pro_clip_id: 'psc_1',
      text_content: null,
    })
  })

  test('createText → POST /coach/analyses/{id}/annotations', async () => {
    T.request.mockResolvedValueOnce({
      statusCode: 200,
      data: { code: 0, data: { id: 'can_2', annotation_type: 'text' } },
    })
    await coachAnnotationService.createText('ana_x', { text_content: '注意送杆' })
    const sent = T.request.mock.calls[0][0]
    expect(sent.method).toBe('POST')
    expect(sent.url).toMatch(/\/coach\/analyses\/ana_x\/annotations$/)
    expect(sent.data).toEqual({
      annotation_type: 'text',
      text_content: '注意送杆',
    })
  })

  test('remove → DELETE /coach/annotations/{id}', async () => {
    T.request.mockResolvedValueOnce({ statusCode: 200, data: { code: 0, data: {} } })
    await coachAnnotationService.remove('can_9')
    const sent = T.request.mock.calls[0][0]
    expect(sent.method).toBe('DELETE')
    expect(sent.url).toMatch(/\/coach\/annotations\/can_9$/)
  })
})
