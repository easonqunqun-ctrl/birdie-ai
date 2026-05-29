/**
 * P2-M12-03 · 球手详情页：球手头部 + 镜头列表（按机位分组）。
 *
 * 数据契约
 * --------
 * - 镜头默认全部机位；提供 face_on / down_the_line 两种过滤切换
 * - 镜头版权来源 (source_credit) 在每条镜头底部显示，合规要求
 */

import { FC, useCallback, useState } from 'react'
import { View, Text, ScrollView, Image } from '@tarojs/components'
import Taro, { useDidShow, useRouter } from '@tarojs/taro'
import { PHASE2_PROS_ENABLED_FLAG } from '@/constants/flags'
import {
  prosService,
  type ProCameraAngle,
  type ProPlayerRead,
  type ProSwingClipRead,
} from '@/services/prosService'
import './detail.scss'

type FilterValue = 'all' | ProCameraAngle

const FILTERS: { key: FilterValue; label: string }[] = [
  { key: 'all', label: '全部' },
  { key: 'face_on', label: '正面' },
  { key: 'down_the_line', label: '侧线' },
]

const ProDetailPage: FC = () => {
  const router = useRouter()
  const playerId = router.params.id

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [player, setPlayer] = useState<ProPlayerRead | null>(null)
  const [clips, setClips] = useState<ProSwingClipRead[]>([])
  const [filter, setFilter] = useState<FilterValue>('all')

  const load = useCallback(
    async (cameraAngle: FilterValue) => {
      if (!playerId) {
        setError('参数错误')
        setLoading(false)
        return
      }
      setLoading(true)
      setError(null)
      try {
        const detailPromise = prosService.detail(playerId)
        const clipsPromise = prosService.clips(
          playerId,
          cameraAngle === 'all' ? {} : { camera_angle: cameraAngle },
        )
        const [d, c] = await Promise.all([detailPromise, clipsPromise])
        setPlayer(d)
        setClips(c)
      } catch (e) {
        const msg = e instanceof Error ? e.message : '加载失败'
        setError(msg)
      } finally {
        setLoading(false)
      }
    },
    [playerId],
  )

  useDidShow(() => {
    if (!PHASE2_PROS_ENABLED_FLAG) {
      Taro.showToast({ title: '该功能尚未开放', icon: 'none' })
      setTimeout(() => Taro.navigateBack({ delta: 1 }), 1200)
      return
    }
    void load(filter)
  })

  const onFilterChange = (key: FilterValue) => {
    setFilter(key)
    void load(key)
  }

  if (!PHASE2_PROS_ENABLED_FLAG) {
    return (
      <View className='pro-detail pro-detail--blocked'>
        <Text>功能维护中…</Text>
      </View>
    )
  }

  if (loading) {
    return (
      <View className='pro-detail pro-detail--empty'>
        <Text>加载中…</Text>
      </View>
    )
  }

  if (error || !player) {
    return (
      <View className='pro-detail pro-detail--empty'>
        <Text className='pro-detail__error'>{error ?? '球手不存在'}</Text>
        <View
          className='pro-detail__back'
          onClick={() => Taro.navigateBack({ delta: 1 })}
        >
          <Text>返回</Text>
        </View>
      </View>
    )
  }

  return (
    <ScrollView scrollY className='pro-detail'>
      <View className='pro-detail__header'>
        {player.avatar_url ? (
          <Image
            className='pro-detail__avatar'
            src={player.avatar_url}
            mode='aspectFill'
          />
        ) : (
          <View className='pro-detail__avatar pro-detail__avatar--placeholder'>
            <Text>{player.name.slice(0, 1)}</Text>
          </View>
        )}
        <View className='pro-detail__header-main'>
          <Text className='pro-detail__name'>{player.name}</Text>
          {player.name_en && (
            <Text className='pro-detail__name-en'>{player.name_en}</Text>
          )}
          <View className='pro-detail__meta'>
            {player.nationality && (
              <Text className='pro-detail__meta-item'>{player.nationality}</Text>
            )}
            <Text className='pro-detail__meta-item'>
              {player.handedness === 'right' ? '右手' : '左手'}
            </Text>
            {player.height_cm && (
              <Text className='pro-detail__meta-item'>{player.height_cm}cm</Text>
            )}
          </View>
        </View>
      </View>

      {player.short_bio && (
        <View className='pro-detail__bio'>
          <Text>{player.short_bio}</Text>
        </View>
      )}

      <View className='pro-detail__filters'>
        {FILTERS.map((f) => (
          <View
            key={f.key}
            className={`pro-detail__filter ${
              filter === f.key ? 'pro-detail__filter--active' : ''
            }`}
            onClick={() => onFilterChange(f.key)}
          >
            <Text>{f.label}</Text>
          </View>
        ))}
      </View>

      <View className='pro-detail__clips'>
        {clips.length === 0 ? (
          <View className='pro-detail__clips-empty'>
            <Text>该机位暂无镜头</Text>
          </View>
        ) : (
          clips.map((clip) => (
            <View key={clip.id} className='pro-detail__clip-card'>
              {clip.thumbnail_url && (
                <Image
                  className='pro-detail__clip-thumb'
                  src={clip.thumbnail_url}
                  mode='aspectFill'
                />
              )}
              <View className='pro-detail__clip-main'>
                <Text className='pro-detail__clip-title'>
                  {clip.club_type} · {clip.camera_angle === 'face_on' ? '正面' : '侧线'}
                </Text>
                <View className='pro-detail__clip-meta'>
                  {clip.duration_ms && (
                    <Text className='pro-detail__clip-meta-item'>
                      {(clip.duration_ms / 1000).toFixed(1)}s
                    </Text>
                  )}
                  {clip.fps && (
                    <Text className='pro-detail__clip-meta-item'>{clip.fps}fps</Text>
                  )}
                  {clip.overall_score != null && (
                    <Text className='pro-detail__clip-meta-item pro-detail__clip-score'>
                      {clip.overall_score}分
                    </Text>
                  )}
                </View>
                <Text className='pro-detail__clip-credit'>
                  来源：{clip.source_credit}
                </Text>
              </View>
              <View className='pro-detail__clip-actions'>
                <View
                  className='pro-detail__clip-cta pro-detail__clip-cta--pgc'
                  onClick={(e) => {
                    e.stopPropagation?.()
                    Taro.navigateTo({
                      url: `/pages/pros/clip-insight?clipId=${encodeURIComponent(clip.id)}&playerId=${encodeURIComponent(playerId || player.id)}`,
                    })
                  }}
                >
                  <Text>解说</Text>
                </View>
                <View
                  className='pro-detail__clip-cta'
                  onClick={() =>
                    Taro.showToast({
                      title: '视频播放将在后续版本上线',
                      icon: 'none',
                    })
                  }
                >
                  <Text>▶</Text>
                </View>
              </View>
            </View>
          ))
        )}
      </View>
    </ScrollView>
  )
}

export default ProDetailPage
