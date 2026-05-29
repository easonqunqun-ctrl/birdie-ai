import { meetupEventService } from '../meetupEventService'

jest.mock('../request', () => ({
  http: {
    get: jest.fn(),
    post: jest.fn(),
  },
}))

const { http } = jest.requireMock('../request') as {
  http: { get: jest.Mock; post: jest.Mock }
}

describe('meetupEventService', () => {
  beforeEach(() => {
    jest.clearAllMocks()
  })

  it('lists templates', async () => {
    http.get.mockResolvedValue([{ code: 'putting_contest', label: '推杆挑战赛' }])
    const res = await meetupEventService.listTemplates()
    expect(http.get).toHaveBeenCalledWith('/meetups/events/templates')
    expect(res[0].code).toBe('putting_contest')
  })

  it('creates event', async () => {
    http.post.mockResolvedValue({ id: 'soe_1', title: '周末赛' })
    await meetupEventService.create({
      title: '周末赛',
      template_code: 'distance_contest',
    })
    expect(http.post).toHaveBeenCalledWith('/meetups/events', {
      title: '周末赛',
      template_code: 'distance_contest',
    })
  })

  it('submits score', async () => {
    http.post.mockResolvedValue({ id: 'soe_1' })
    await meetupEventService.submitScore('soe_1', { self_reported_score: 7 })
    expect(http.post).toHaveBeenCalledWith('/meetups/events/soe_1/submit-score', {
      self_reported_score: 7,
    })
  })
})
