/**
 * P2-M13-05 · 约球邀请列表
 */

import { FC, useCallback, useState } from 'react'
import { View, Text, ScrollView, Button } from '@tarojs/components'
import Taro, { useDidShow } from '@tarojs/taro'
import { PHASE2_MEETUP_ENABLED_FLAG } from '@/constants/flags'
import {
  INVITATION_STATUS_LABEL,
  MEETUP_ROLE_TAB,
  type MeetupListRole,
} from '@/constants/meetup'
import { meetupService, type MeetupInvitationRead } from '@/services/meetupService'
import { useUserStore } from '@/store/userStore'
import './index.scss'

function formatWhen(iso: string | null): string {
  if (!iso) return '时间待定'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getMonth() + 1}/${d.getDate()} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

const MeetupListPage: FC = () => {
  const userId = useUserStore((s) => s.user?.id)
  const [role, setRole] = useState<MeetupListRole>('any')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [items, setItems] = useState<MeetupInvitationRead[]>([])

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await meetupService.listInvitations({ role, limit: 50 })
      setItems(res.items)
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }, [role])

  useDidShow(() => {
    if (!PHASE2_MEETUP_ENABLED_FLAG) {
      Taro.showToast({ title: '该功能尚未开放', icon: 'none' })
      setTimeout(() => Taro.navigateBack({ delta: 1 }), 1200)
      return
    }
    void load()
  })

  const roleLabel = (it: MeetupInvitationRead): string => {
    if (!userId) return ''
    if (it.inviter_user_id === userId) return '我发出的'
    if (it.invitee_user_id === userId) return '收到的'
    return ''
  }

  const onTap = (it: MeetupInvitationRead) => {
    Taro.navigateTo({
      url: `/pages/meetup/detail?id=${encodeURIComponent(it.id)}`,
    })
  }

  const goCreate = () => {
    Taro.navigateTo({ url: '/pages/meetup/create' })
  }

  if (!PHASE2_MEETUP_ENABLED_FLAG) {
    return (
      <View className='meetup-list meetup-list--blocked'>
        <Text>功能维护中…</Text>
      </View>
    )
  }

  return (
    <View className='meetup-list'>
      <View className='meetup-list__tabs'>
        {MEETUP_ROLE_TAB.map((tab) => (
          <View
            key={tab.key}
            className={[
              'meetup-list__tab',
              role === tab.key ? 'meetup-list__tab--active' : '',
            ]
              .filter(Boolean)
              .join(' ')}
            onClick={() => setRole(tab.key)}
          >
            <Text>{tab.label}</Text>
          </View>
        ))}
      </View>

      {loading && (
        <View className='meetup-list__empty'>
          <Text>加载中…</Text>
        </View>
      )}

      {!loading && error && (
        <View className='meetup-list__empty'>
          <Text className='meetup-list__error'>{error}</Text>
          <View className='meetup-list__retry' onClick={() => void load()}>
            <Text>重试</Text>
          </View>
        </View>
      )}

      {!loading && !error && items.length === 0 && (
        <View className='meetup-list__empty'>
          <Text>暂无约球邀请</Text>
          <Text className='meetup-list__hint'>发起一次约球，邀请球友一起练球</Text>
        </View>
      )}

      {!loading && !error && items.length > 0 && (
        <ScrollView scrollY className='meetup-list__scroll'>
          {items.map((it) => (
            <View key={it.id} className='meetup-list__card' onClick={() => onTap(it)}>
              <View className='meetup-list__card-top'>
                <Text className='meetup-list__role'>{roleLabel(it)}</Text>
                <Text
                  className={[
                    'meetup-list__status',
                    it.status === 'pending' ? 'meetup-list__status--pending' : '',
                    it.status === 'accepted' ? 'meetup-list__status--accepted' : '',
                  ]
                    .filter(Boolean)
                    .join(' ')}
                >
                  {INVITATION_STATUS_LABEL[it.status]}
                </Text>
              </View>
              <Text className='meetup-list__time'>{formatWhen(it.proposed_time)}</Text>
              <Text className='meetup-list__meta'>创建于 {formatWhen(it.created_at)}</Text>
            </View>
          ))}
        </ScrollView>
      )}

      <View className='meetup-list__fab-wrap'>
        <Button className='meetup-list__fab' onClick={goCreate}>
          发起约球
        </Button>
      </View>
    </View>
  )
}

export default MeetupListPage
