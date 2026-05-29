import { meetupSafetyService } from '../meetupSafetyService'

jest.mock('../request', () => ({
  http: {
    get: jest.fn(),
    post: jest.fn(),
    patch: jest.fn(),
  },
}))

const { http } = jest.requireMock('../request') as {
  http: { get: jest.Mock; post: jest.Mock; patch: jest.Mock }
}

describe('meetupSafetyService', () => {
  beforeEach(() => {
    jest.clearAllMocks()
  })

  it('loads safety status', async () => {
    http.get.mockResolvedValue({ can_use_meetup: false })
    const res = await meetupSafetyService.status()
    expect(http.get).toHaveBeenCalledWith('/meetups/safety/status')
    expect(res.can_use_meetup).toBe(false)
  })

  it('accepts tos', async () => {
    http.post.mockResolvedValue({ can_use_meetup: true })
    await meetupSafetyService.acceptTos()
    expect(http.post).toHaveBeenCalledWith('/meetups/safety/accept-tos', {
      gender_preference: undefined,
    })
  })

  it('updates spectator opt-in', async () => {
    http.patch.mockResolvedValue({ coach_spectator_optin: true })
    await meetupSafetyService.updateSpectatorOptin(true)
    expect(http.patch).toHaveBeenCalledWith('/meetups/safety/spectator-optin', {
      coach_spectator_optin: true,
    })
  })
})
