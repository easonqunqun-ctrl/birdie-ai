import { yardageBookService } from '@/services/yardageBookService'

jest.mock('@/services/request', () => ({
  http: {
    get: jest.fn(),
    put: jest.fn(),
  },
}))

const { http } = jest.requireMock('@/services/request')

describe('yardageBookService', () => {
  beforeEach(() => {
    jest.clearAllMocks()
  })

  test('getMine calls GET /users/me/yardage-book', async () => {
    http.get.mockResolvedValue({ clubs: [] })
    await yardageBookService.getMine()
    expect(http.get).toHaveBeenCalledWith('/users/me/yardage-book')
  })

  test('updateMine calls PUT with clubs payload', async () => {
    http.put.mockResolvedValue({ clubs: [] })
    await yardageBookService.updateMine([{ club_id: 'ucb_1', self_yardage_m: 140 }])
    expect(http.put).toHaveBeenCalledWith('/users/me/yardage-book', {
      clubs: [{ club_id: 'ucb_1', self_yardage_m: 140 }],
    })
  })
})
