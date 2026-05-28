/**
 * P2-M13-05 · meetupService 客户端单测
 */

import { meetupService } from '@/services/meetupService'
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

describe('meetupService', () => {
  test('listInvitations default → GET /users/me/meetup-invitations', async () => {
    T.request.mockResolvedValueOnce(ok({ items: [], total: 0, role: 'any', status: null }))
    await meetupService.listInvitations()
    const sent = T.request.mock.calls[0][0]
    expect(sent.method).toBe('GET')
    expect(sent.url).toMatch(/\/users\/me\/meetup-invitations$/)
  })

  test('listInvitations with role + status → query string', async () => {
    T.request.mockResolvedValueOnce(ok({ items: [], total: 0, role: 'invitee', status: 'pending' }))
    await meetupService.listInvitations({ role: 'invitee', status: 'pending', limit: 20 })
    const url: string = T.request.mock.calls[0][0].url
    expect(url).toContain('role=invitee')
    expect(url).toContain('status=pending')
    expect(url).toContain('limit=20')
  })

  test('createInvitation → POST /meetups/invitations', async () => {
    T.request.mockResolvedValueOnce(
      ok({
        id: 'mvi_1',
        inviter_user_id: 'usr_a',
        invitee_user_id: 'usr_b',
        venue_id: null,
        proposed_time: null,
        expires_at: null,
        status: 'pending',
        accepted_at: null,
        contact_payload: null,
        created_at: '2026-05-27T00:00:00Z',
      }),
    )
    await meetupService.createInvitation({
      invitee_user_id: 'usr_b',
      message: '一起练球',
    })
    const sent = T.request.mock.calls[0][0]
    expect(sent.method).toBe('POST')
    expect(sent.url).toMatch(/\/meetups\/invitations$/)
    expect(sent.data.invitee_user_id).toBe('usr_b')
  })

  test('acceptInvitation → POST .../accept with body', async () => {
    T.request.mockResolvedValueOnce(ok({ id: 'mvi_1', status: 'accepted' }))
    await meetupService.acceptInvitation('mvi_1', { note: '门口见', meet_at: '8点' })
    const sent = T.request.mock.calls[0][0]
    expect(sent.url).toMatch(/\/meetups\/invitations\/mvi_1\/accept$/)
    expect(sent.data.note).toBe('门口见')
  })

  test('declineInvitation → POST .../decline', async () => {
    T.request.mockResolvedValueOnce(ok({ id: 'mvi_1', status: 'declined' }))
    await meetupService.declineInvitation('mvi_2')
    expect(T.request.mock.calls[0][0].url).toMatch(/\/meetups\/invitations\/mvi_2\/decline$/)
  })

  test('cancelInvitation → POST .../cancel', async () => {
    T.request.mockResolvedValueOnce(ok({ id: 'mvi_1', status: 'cancelled' }))
    await meetupService.cancelInvitation('mvi_3')
    expect(T.request.mock.calls[0][0].url).toMatch(/\/meetups\/invitations\/mvi_3\/cancel$/)
  })

  test('nearbyVenues → GET /venues/nearby with lat/lng', async () => {
    T.request.mockResolvedValueOnce(ok({ items: [], total: 0, center_latitude: 31, center_longitude: 121, radius_km: 5 }))
    await meetupService.nearbyVenues({ lat: 31.2, lng: 121.5, radius_km: 3 })
    const url: string = T.request.mock.calls[0][0].url
    expect(url).toContain('/venues/nearby')
    expect(url).toContain('lat=31.2')
    expect(url).toContain('lng=121.5')
    expect(url).toContain('radius_km=3')
  })
})
