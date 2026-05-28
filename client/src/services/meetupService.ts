/**
 * P2-M13-05 · 约球客户端 service。
 *
 * 对齐 backend meetups / meetup_responses / venues（M13-02～M13-04）：
 * - GET  /users/me/meetup-invitations
 * - POST /meetups/invitations
 * - POST /meetups/invitations/{id}/cancel | accept | decline
 * - GET  /venues/nearby · /venues/{id}
 *
 * 灰度：`PHASE2_MEETUP_ENABLED_FLAG`（constants/flags.ts）
 */

import { http } from './request'
import type { InvitationStatus, MeetupListRole, VenueType } from '@/constants/meetup'

export interface MeetupInvitationRead {
  id: string
  inviter_user_id: string
  invitee_user_id: string
  venue_id: string | null
  proposed_time: string | null
  expires_at: string | null
  status: InvitationStatus
  accepted_at: string | null
  contact_payload: { note?: string; meet_at?: string } | null
  created_at: string
}

export interface MeetupInvitationListResponse {
  items: MeetupInvitationRead[]
  total: number
  role: string
  status: string | null
}

export interface MeetupInvitationCreate {
  invitee_user_id: string
  venue_id?: string | null
  proposed_time?: string | null
  expires_at?: string | null
  message?: string | null
}

export interface MeetupInvitationAcceptPayload {
  note?: string | null
  meet_at?: string | null
}

export interface VenueRead {
  id: string
  city: string
  name: string
  venue_type: VenueType
  address: string | null
  source: string
  status: string
  latitude: string | number | null
  longitude: string | number | null
}

export interface VenueNearbyItem extends VenueRead {
  distance_km: number
  latitude: number
  longitude: number
}

export interface VenueNearbyResponse {
  items: VenueNearbyItem[]
  total: number
  center_latitude: number
  center_longitude: number
  radius_km: number
}

export interface ListMeetupInvitationsQuery {
  role?: MeetupListRole
  status?: InvitationStatus
  limit?: number
}

export interface NearbyVenuesQuery {
  lat: number
  lng: number
  radius_km?: number
  venue_type?: VenueType
  limit?: number
}

export const meetupService = {
  listInvitations(query: ListMeetupInvitationsQuery = {}) {
    const qs: string[] = []
    if (query.role) qs.push(`role=${encodeURIComponent(query.role)}`)
    if (query.status) qs.push(`status=${encodeURIComponent(query.status)}`)
    if (query.limit != null) qs.push(`limit=${query.limit}`)
    const tail = qs.length ? `?${qs.join('&')}` : ''
    return http.get<MeetupInvitationListResponse>(`/users/me/meetup-invitations${tail}`)
  },

  createInvitation(payload: MeetupInvitationCreate) {
    return http.post<MeetupInvitationRead>('/meetups/invitations', payload)
  },

  cancelInvitation(invitationId: string) {
    return http.post<MeetupInvitationRead>(
      `/meetups/invitations/${encodeURIComponent(invitationId)}/cancel`,
    )
  },

  acceptInvitation(invitationId: string, payload?: MeetupInvitationAcceptPayload) {
    return http.post<MeetupInvitationRead>(
      `/meetups/invitations/${encodeURIComponent(invitationId)}/accept`,
      payload ?? {},
    )
  },

  declineInvitation(invitationId: string) {
    return http.post<MeetupInvitationRead>(
      `/meetups/invitations/${encodeURIComponent(invitationId)}/decline`,
    )
  },

  nearbyVenues(query: NearbyVenuesQuery) {
    const qs = [
      `lat=${query.lat}`,
      `lng=${query.lng}`,
      `radius_km=${query.radius_km ?? 5}`,
    ]
    if (query.venue_type) qs.push(`venue_type=${query.venue_type}`)
    if (query.limit != null) qs.push(`limit=${query.limit}`)
    return http.get<VenueNearbyResponse>(`/venues/nearby?${qs.join('&')}`)
  },

  venueDetail(venueId: string) {
    return http.get<VenueRead>(`/venues/${encodeURIComponent(venueId)}`)
  },
}
