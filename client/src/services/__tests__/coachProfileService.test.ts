import { coachProfileService } from '../coachProfileService'

jest.mock('../request', () => ({
  http: {
    get: jest.fn(),
    post: jest.fn(),
  },
}))

const { http } = jest.requireMock('../request') as {
  http: { get: jest.Mock; post: jest.Mock }
}

describe('coachProfileService', () => {
  beforeEach(() => {
    jest.clearAllMocks()
  })

  it('submits coach apply', async () => {
    http.post.mockResolvedValue({ status: 'pending' })
    await coachProfileService.apply({
      display_name: '张教练',
      level: 'china_pga',
    })
    expect(http.post).toHaveBeenCalledWith('/coach/profile/apply', {
      display_name: '张教练',
      level: 'china_pga',
    })
  })

  it('loads my coach profile', async () => {
    http.get.mockResolvedValue(null)
    const res = await coachProfileService.me()
    expect(http.get).toHaveBeenCalledWith('/coach/profile/me')
    expect(res).toBeNull()
  })
})
