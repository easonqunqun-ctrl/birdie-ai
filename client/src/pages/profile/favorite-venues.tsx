/**
 * P2-M9-05 · 常去球馆页：列表 / 附近添加 / 删除。
 *
 * API
 * ---
 * - GET  /users/me/profile-v2/favorite-venues
 * - PUT  /users/me/profile-v2 → favorite_course_ids
 * - GET  /venues/nearby（添加时定位）
 */

import { FC, useCallback, useState } from 'react'
import { View, Text, ScrollView } from '@tarojs/components'
import Taro, { useDidShow } from '@tarojs/taro'
import MeetupTosModal from '@/components/MeetupTosModal'
import {
  getCurrentGcj02Location,
  LocationError,
  promptOpenLocationSettings,
} from '@/adapters/location'
import { MAX_FAVORITE_VENUES } from '@/constants/profileV2'
import { PHASE2_PROFILE_V2_ENABLED_FLAG } from '@/constants/flags'
import { VENUE_TYPE_LABEL } from '@/constants/meetup'
import {
  profileV2Service,
  type FavoriteVenueRead,
  type FavoriteVenuesList,
} from '@/services/profileV2'
import { meetupService, type VenueNearbyItem } from '@/services/meetupService'
import { isRequestError } from '@/services/request'
import { handleMeetupGateError, navigateToMeetupIdentityVerify } from '@/utils/meetupGate'
import './favorite-venues.scss'

const FavoriteVenuesPage: FC = () => {
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [data, setData] = useState<FavoriteVenuesList | null>(null)
  const [pickerOpen, setPickerOpen] = useState(false)
  const [nearby, setNearby] = useState<VenueNearbyItem[]>([])
  const [locating, setLocating] = useState(false)
  const [showTos, setShowTos] = useState(false)

  const venueRedirect = '/pages/profile/favorite-venues'

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const resp = await profileV2Service.listFavoriteVenues()
      setData(resp)
    } catch (e) {
      const msg = e instanceof Error ? e.message : '加载失败'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }, [])

  useDidShow(() => {
    if (!PHASE2_PROFILE_V2_ENABLED_FLAG) {
      Taro.showToast({ title: '该功能尚未开放', icon: 'none' })
      setTimeout(() => Taro.navigateBack({ delta: 1 }), 1200)
      return
    }
    void load()
  })

  const saveIds = async (ids: string[]) => {
    setSaving(true)
    try {
      await profileV2Service.update({ favorite_course_ids: ids })
      Taro.showToast({ title: '已保存', icon: 'success' })
      await load()
    } catch (e) {
      const msg = e instanceof Error ? e.message : '保存失败'
      Taro.showToast({ title: msg, icon: 'none' })
    } finally {
      setSaving(false)
    }
  }

  const handleRemove = async (venue: FavoriteVenueRead) => {
    if (!data) return
    const res = await Taro.showModal({
      title: '确认移除',
      content: `从常去球馆移除「${venue.name}」？`,
    })
    if (!res.confirm) return
    const nextIds = data.items.filter((v) => v.id !== venue.id).map((v) => v.id)
    await saveIds(nextIds)
  }

  const fetchNearby = async () => {
    if (!data) return
    const loc = await getCurrentGcj02Location()
    const resp = await meetupService.nearbyVenues({
      lat: loc.latitude,
      lng: loc.longitude,
      radius_km: 8,
      limit: 20,
    })
    const existing = new Set(data.items.map((v) => v.id))
    const candidates = resp.items.filter((v) => !existing.has(v.id))
    if (candidates.length === 0) {
      Taro.showToast({ title: '附近暂无可用球馆', icon: 'none' })
      return
    }
    setNearby(candidates)
    setPickerOpen(true)
  }

  const handleOpenPicker = async () => {
    if (!data || data.total >= MAX_FAVORITE_VENUES) {
      Taro.showToast({ title: `最多 ${MAX_FAVORITE_VENUES} 个`, icon: 'none' })
      return
    }
    setLocating(true)
    try {
      await fetchNearby()
    } catch (e) {
      if (e instanceof LocationError && e.code === 'denied') {
        const opened = await promptOpenLocationSettings()
        if (opened) {
          try {
            await fetchNearby()
            return
          } catch (retryErr) {
            if (
              await handleMeetupGateError(retryErr, {
                redirect: venueRedirect,
                onTosRequired: () => setShowTos(true),
              })
            ) {
              return
            }
            const msg =
              retryErr instanceof Error ? retryErr.message : '定位失败，请稍后重试'
            Taro.showToast({ title: msg, icon: 'none' })
            return
          }
        }
        return
      }
      if (
        await handleMeetupGateError(e, {
          redirect: venueRedirect,
          onTosRequired: () => setShowTos(true),
        })
      ) {
        return
      }
      const msg = isRequestError(e)
        ? e.message
        : e instanceof Error
          ? e.message
          : '定位失败，请稍后重试'
      Taro.showToast({ title: msg, icon: 'none' })
    } finally {
      setLocating(false)
    }
  }

  const handlePickVenue = async (venue: VenueNearbyItem) => {
    if (!data) return
    const nextIds = [...data.items.map((v) => v.id), venue.id]
    setPickerOpen(false)
    setNearby([])
    await saveIds(nextIds)
  }

  if (!PHASE2_PROFILE_V2_ENABLED_FLAG) {
    return (
      <View className='favorite-venues favorite-venues--blocked'>
        <Text>功能维护中…</Text>
      </View>
    )
  }

  if (loading) {
    return (
      <View className='favorite-venues favorite-venues--empty'>
        <Text>加载中…</Text>
      </View>
    )
  }

  if (error) {
    return (
      <View className='favorite-venues favorite-venues--empty'>
        <Text className='favorite-venues__error'>{error}</Text>
        <View className='favorite-venues__retry' onClick={() => void load()}>
          <Text>重试</Text>
        </View>
      </View>
    )
  }

  const total = data?.total ?? 0
  const remaining = MAX_FAVORITE_VENUES - total

  return (
    <View className='favorite-venues'>
      <View className='favorite-venues__header'>
        <Text className='favorite-venues__title'>常去球馆</Text>
        <Text className='favorite-venues__count'>
          {total} / {MAX_FAVORITE_VENUES}
        </Text>
      </View>

      {(data?.missing_ids?.length ?? 0) > 0 && (
        <Text className='favorite-venues__warning'>
          有 {data!.missing_ids.length} 个球馆已下线，保存时将自动清理。
        </Text>
      )}

      <ScrollView scrollY className='favorite-venues__list'>
        {total === 0 && (
          <View className='favorite-venues__empty-hint'>
            <Text>添加常去球馆，便于约球与个性化推荐</Text>
          </View>
        )}
        {data?.items.map((venue) => (
          <View key={venue.id} className='favorite-venues__card'>
            <View className='favorite-venues__card-main'>
              <Text className='favorite-venues__card-name'>{venue.name}</Text>
              <Text className='favorite-venues__card-meta'>
                {venue.city} · {VENUE_TYPE_LABEL[venue.venue_type]}
              </Text>
            </View>
            <View
              className='favorite-venues__remove'
              onClick={() => !saving && void handleRemove(venue)}
            >
              <Text>移除</Text>
            </View>
          </View>
        ))}
      </ScrollView>

      {pickerOpen && (
        <View className='favorite-venues__picker'>
          <Text className='favorite-venues__picker-title'>附近球馆（点击添加）</Text>
          {nearby.map((v) => (
            <View
              key={v.id}
              className='favorite-venues__picker-item'
              onClick={() => !saving && void handlePickVenue(v)}
            >
              <Text className='favorite-venues__picker-name'>{v.name}</Text>
              <Text className='favorite-venues__picker-meta'>
                {v.distance_km.toFixed(1)} km
              </Text>
            </View>
          ))}
          <View
            className='favorite-venues__cancel-picker'
            onClick={() => {
              setPickerOpen(false)
              setNearby([])
            }}
          >
            <Text>取消</Text>
          </View>
        </View>
      )}

      <View className='favorite-venues__footer'>
        <View
          className={[
            'favorite-venues__add-btn',
            remaining <= 0 || locating || saving ? 'favorite-venues__add-btn--disabled' : '',
          ].join(' ')}
          onClick={() => !locating && !saving && void handleOpenPicker()}
        >
          <Text>{locating ? '定位中…' : remaining > 0 ? '添加附近球馆' : '已达上限'}</Text>
        </View>
      </View>

      <MeetupTosModal
        visible={showTos}
        onAccepted={() => {
          setShowTos(false)
          void fetchNearby().catch((e) => {
            void handleMeetupGateError(e, { redirect: venueRedirect })
          })
        }}
        onRejected={() => setShowTos(false)}
        onIdentityRequired={() => {
          setShowTos(false)
          navigateToMeetupIdentityVerify(venueRedirect)
        }}
      />
    </View>
  )
}

export default FavoriteVenuesPage
