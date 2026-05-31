import {
  MEETUP_ERROR_IDENTITY,
  MEETUP_ERROR_MINOR,
  MEETUP_ERROR_TOS,
  buildMeetupIdentityVerifyUrl,
  getMeetupErrorCode,
  resolveMeetupGateAction,
} from '@/utils/meetupGate'
import { RequestError } from '@/services/request'

describe('meetupGate', () => {
  test('getMeetupErrorCode from RequestError', () => {
    const err = new RequestError('business', '请先完成手机号实名', { code: 40333 })
    expect(getMeetupErrorCode(err)).toBe(40333)
  })

  test('resolveMeetupGateAction', () => {
    expect(
      resolveMeetupGateAction(
        new RequestError('business', 'x', { code: MEETUP_ERROR_IDENTITY }),
      ),
    ).toBe('identity')
    expect(
      resolveMeetupGateAction(new RequestError('business', 'x', { code: MEETUP_ERROR_MINOR })),
    ).toBe('minor')
    expect(
      resolveMeetupGateAction(new RequestError('business', 'x', { code: MEETUP_ERROR_TOS })),
    ).toBe('tos')
    expect(resolveMeetupGateAction(new Error('other'))).toBeNull()
  })

  test('buildMeetupIdentityVerifyUrl with redirect', () => {
    expect(buildMeetupIdentityVerifyUrl()).toBe('/pages/meetup/identity-verify')
    expect(buildMeetupIdentityVerifyUrl('/pages/profile/favorite-venues')).toBe(
      '/pages/meetup/identity-verify?redirect=%2Fpages%2Fprofile%2Ffavorite-venues',
    )
  })
})
