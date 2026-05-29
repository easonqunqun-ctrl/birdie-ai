import { coachSpectatorService } from '../coachSpectatorService'

jest.mock('../request', () => ({
  http: {
    get: jest.fn(),
  },
}))

const { http } = jest.requireMock('../request') as {
  http: { get: jest.Mock }
}

describe('coachSpectatorService', () => {
  beforeEach(() => {
    jest.clearAllMocks()
  })

  it('lists student meetups for coach', async () => {
    http.get.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20, student_user_id: 'usr_s' })
    const res = await coachSpectatorService.listStudentMeetups('usr_s', { page: 1 })
    expect(http.get).toHaveBeenCalledWith('/coach/students/usr_s/meetups?page=1')
    expect(res.student_user_id).toBe('usr_s')
  })
})
