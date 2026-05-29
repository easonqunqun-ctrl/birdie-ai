import { meetupFeedbackService } from '@/services/meetupFeedbackService'
import Taro from '@tarojs/taro'

const T = Taro as unknown as Record<string, jest.Mock>

beforeEach(() => {
  T.request.mockReset()
})

describe('meetupFeedbackService', () => {
  test('submit → POST /meetups/feedbacks', async () => {
    T.request.mockResolvedValueOnce({
      statusCode: 200,
      data: { code: 0, data: { id: 'mfb_1' } },
    })
    await meetupFeedbackService.submit({
      invitation_id: 'mvi_1',
      rating: 5,
      tags: ['on_time'],
    })
    const sent = T.request.mock.calls[0][0]
    expect(sent.method).toBe('POST')
    expect(sent.url).toMatch(/\/meetups\/feedbacks$/)
  })

  test('eligibility → GET /meetups/feedbacks/eligibility', async () => {
    T.request.mockResolvedValueOnce({
      statusCode: 200,
      data: { code: 0, data: { can_submit: true, has_submitted: false, peer_visible: false } },
    })
    await meetupFeedbackService.eligibility('mvi_1')
    const sent = T.request.mock.calls[0][0]
    expect(sent.method).toBe('GET')
    expect(sent.url).toContain('/meetups/feedbacks/eligibility')
  })
})
