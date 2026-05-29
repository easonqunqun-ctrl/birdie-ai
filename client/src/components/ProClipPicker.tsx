/**
 * M12-09 · 职业镜头选择弹层（教练批注 video_ref）。
 */

import { FC, useCallback, useEffect, useState } from 'react'
import { View, Text, ScrollView, Image } from '@tarojs/components'
import Taro from '@tarojs/taro'
import { PHASE2_PROS_ENABLED_FLAG } from '@/constants/flags'
import {
  prosService,
  type ProPlayerRead,
  type ProSwingClipRead,
} from '@/services/prosService'
import './ProClipPicker.scss'

export interface ProClipPickerProps {
  visible: boolean
  onClose: () => void
  onSelect: (clip: ProSwingClipRead, player: ProPlayerRead) => void
}

const ProClipPicker: FC<ProClipPickerProps> = ({ visible, onClose, onSelect }) => {
  const [loading, setLoading] = useState(false)
  const [players, setPlayers] = useState<ProPlayerRead[]>([])
  const [selectedPlayer, setSelectedPlayer] = useState<ProPlayerRead | null>(null)
  const [clips, setClips] = useState<ProSwingClipRead[]>([])

  const loadPlayers = useCallback(async () => {
    if (!PHASE2_PROS_ENABLED_FLAG) return
    setLoading(true)
    try {
      const list = await prosService.list()
      setPlayers(list)
    } catch (e) {
      Taro.showToast({
        title: e instanceof Error ? e.message : '加载球手库失败',
        icon: 'none',
      })
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (!visible) {
      setSelectedPlayer(null)
      setClips([])
      return
    }
    void loadPlayers()
  }, [visible, loadPlayers])

  const pickPlayer = async (player: ProPlayerRead) => {
    setSelectedPlayer(player)
    setLoading(true)
    try {
      const list = await prosService.clips(player.id)
      setClips(list)
    } catch (e) {
      Taro.showToast({
        title: e instanceof Error ? e.message : '加载镜头失败',
        icon: 'none',
      })
    } finally {
      setLoading(false)
    }
  }

  if (!visible) return null

  return (
    <View className='pro-clip-picker'>
      <View className='pro-clip-picker__mask' onClick={onClose} />
      <View className='pro-clip-picker__panel'>
        <View className='pro-clip-picker__head'>
          <Text className='pro-clip-picker__title'>
            {selectedPlayer ? `选择 ${selectedPlayer.name} 的镜头` : '选择球手'}
          </Text>
          {selectedPlayer ? (
            <Text className='pro-clip-picker__back' onClick={() => setSelectedPlayer(null)}>
              返回
            </Text>
          ) : (
            <Text className='pro-clip-picker__back' onClick={onClose}>
              关闭
            </Text>
          )}
        </View>
        <ScrollView scrollY className='pro-clip-picker__list'>
          {loading && (
            <Text className='pro-clip-picker__hint'>加载中…</Text>
          )}
          {!selectedPlayer &&
            players.map((p) => (
              <View
                key={p.id}
                className='pro-clip-picker__row'
                onClick={() => void pickPlayer(p)}
              >
                <Text className='pro-clip-picker__row-title'>{p.name}</Text>
                <Text className='pro-clip-picker__row-meta'>{p.nationality ?? ''}</Text>
              </View>
            ))}
          {selectedPlayer &&
            clips.map((c) => (
              <View
                key={c.id}
                className='pro-clip-picker__clip'
                onClick={() => {
                  onSelect(c, selectedPlayer)
                  onClose()
                }}
              >
                {c.thumbnail_url ? (
                  <Image
                    className='pro-clip-picker__thumb'
                    src={c.thumbnail_url}
                    mode='aspectFill'
                  />
                ) : (
                  <View className='pro-clip-picker__thumb pro-clip-picker__thumb--ph' />
                )}
                <View className='pro-clip-picker__clip-main'>
                  <Text className='pro-clip-picker__row-title'>{c.club_type}</Text>
                  <Text className='pro-clip-picker__row-meta'>
                    {c.camera_angle === 'face_on' ? '正面' : '侧线'}
                    {c.overall_score != null ? ` · ${c.overall_score} 分` : ''}
                  </Text>
                </View>
              </View>
            ))}
          {!loading && selectedPlayer && clips.length === 0 && (
            <Text className='pro-clip-picker__hint'>暂无已发布镜头</Text>
          )}
        </ScrollView>
      </View>
    </View>
  )
}

export default ProClipPicker
