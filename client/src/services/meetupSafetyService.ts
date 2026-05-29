/**
 * P2-M13-09 · 约球合规 service。
 */

import { http } from './request'

export type MeetupGenderPreference = 'any' | 'same' | 'coach_only'

export interface MeetupSafetyStatus {
  meetup_tos_accepted_at: string | null
  gender_preference: MeetupGenderPreference
  coach_spectator_optin: boolean
  identity_eligible: boolean
  phone_verified: boolean
  age_years: number | null
  can_use_meetup: boolean
  tos_text_version: string
}

export interface MeetupTosContent {
  version: string
  title: string
  body: string
  disclaimer: string
}

export const MEETUP_GENDER_OPTIONS: {
  value: MeetupGenderPreference
  label: string
}[] = [
  { value: 'any', label: '任意匹配' },
  { value: 'same', label: '仅匹配同性别' },
  { value: 'coach_only', label: '仅匹配教练' },
]

export const meetupSafetyService = {
  getTos(): Promise<MeetupTosContent> {
    return http.get<MeetupTosContent>('/meetups/safety/tos')
  },

  status(): Promise<MeetupSafetyStatus> {
    return http.get<MeetupSafetyStatus>('/meetups/safety/status')
  },

  acceptTos(gender_preference?: MeetupGenderPreference): Promise<MeetupSafetyStatus> {
    return http.post<MeetupSafetyStatus>('/meetups/safety/accept-tos', {
      gender_preference: gender_preference ?? undefined,
    })
  },

  updatePreference(gender_preference: MeetupGenderPreference): Promise<MeetupSafetyStatus> {
    return http.patch<MeetupSafetyStatus>('/meetups/safety/preferences', { gender_preference })
  },

  updateSpectatorOptin(coach_spectator_optin: boolean): Promise<MeetupSafetyStatus> {
    return http.patch<MeetupSafetyStatus>('/meetups/safety/spectator-optin', {
      coach_spectator_optin,
    })
  },
}
