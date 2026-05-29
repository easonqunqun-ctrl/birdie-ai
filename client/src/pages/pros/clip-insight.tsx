/**
 * P2-M12-07 · 职业镜头 PGC 解说 + AI 对比解读页。
 */

import { FC, useCallback, useEffect, useState } from 'react'
import { View, Text, ScrollView, Button } from '@tarojs/components'
import Taro, { useRouter } from '@tarojs/taro'
import { PHASE2_PROS_ENABLED_FLAG } from '@/constants/flags'
import { useUserStore } from '@/store/userStore'
import {
  prosService,
  type ProClipAnnotationRead,
  type ProSwingClipRead,
} from '@/services/prosService'
import { formatPgcTimeMarker } from '@/utils/pgcTimeMarker'
import './clip-insight.scss'

const ClipInsightPage: FC = () => {
  const router = useRouter()
  const clipId = (router.params.clipId || '').trim()
  const playerId = (router.params.playerId || '').trim()
  const analysisId = (router.params.analysisId || '').trim()
  const token = useUserStore((s) => s.token)

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [clip, setClip] = useState<ProSwingClipRead | null>(null)
  const [playerName, setPlayerName] = useState('')
  const [annotations, setAnnotations] = useState<ProClipAnnotationRead[]>([])
  const [insight, setInsight] = useState('')
  const [insightLoading, setInsightLoading] = useState(false)

  const load = useCallback(async () => {
    if (!clipId || !playerId) {
      setError('参数错误')
      setLoading(false)
      return
    }
    setLoading(true)
    setError(null)
    try {
      const [player, clips, ann] = await Promise.all([
        prosService.detail(playerId),
        prosService.clips(playerId),
        prosService.annotations(clipId),
      ])
      const matched = clips.find((c) => c.id === clipId) ?? null
      if (!matched) {
        setError('镜头不存在')
        setLoading(false)
        return
      }
      setClip(matched)
      setPlayerName(player.name)
      setAnnotations(ann.filter((a) => a.annotation_type === 'text'))
      setLoading(false)
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败')
      setLoading(false)
    }
  }, [clipId, playerId])

  useEffect(() => {
    if (!PHASE2_PROS_ENABLED_FLAG) {
      setError('球手对比库尚未开放')
      setLoading(false)
      return
    }
    void load()
  }, [load])

  const handleGenerateInsight = async () => {
    if (!token) {
      Taro.navigateTo({ url: '/pages/login/index' })
      return
    }
    if (!clipId) return
    setInsightLoading(true)
    try {
      const res = await prosService.pgcInsight(clipId, {
        analysis_id: analysisId || undefined,
      })
      setInsight(res.insight)
    } catch (e) {
      Taro.showToast({
        title: e instanceof Error ? e.message : 'AI 解读失败',
        icon: 'none',
      })
    } finally {
      setInsightLoading(false)
    }
  }

  if (loading) {
    return (
      <View className='clip-insight clip-insight--empty'>
        <Text>加载中…</Text>
      </View>
    )
  }

  if (error || !clip) {
    return (
      <View className='clip-insight clip-insight--empty'>
        <Text>{error || '无法加载'}</Text>
        <Button onClick={() => Taro.navigateBack().catch(() => undefined)}>返回</Button>
      </View>
    )
  }

  return (
    <ScrollView scrollY className='clip-insight'>
      <View className='clip-insight__head'>
        <Text className='clip-insight__title'>{playerName}</Text>
        <Text className='clip-insight__meta'>
          {clip.club_type} · {clip.camera_angle === 'face_on' ? '正面' : '侧线'}
          {clip.overall_score != null ? ` · ${clip.overall_score} 分` : ''}
        </Text>
      </View>

      <View className='clip-insight__section'>
        <Text className='clip-insight__section-title'>教练 PGC 解说</Text>
        {annotations.length === 0 ? (
          <Text className='clip-insight__empty'>暂无文字解说</Text>
        ) : (
          annotations.map((ann) => (
            <View key={ann.id} className='clip-insight__ann'>
              <Text className='clip-insight__ann-time'>
                {formatPgcTimeMarker(ann.time_marker_ms)}
              </Text>
              <Text className='clip-insight__ann-text'>{ann.content}</Text>
            </View>
          ))
        )}
      </View>

      <View className='clip-insight__section'>
        <Text className='clip-insight__section-title'>AI 对比解读</Text>
        <Text className='clip-insight__hint'>
          结合职业镜头要点{analysisId ? '与你的分析报告' : ''}，生成可对标的练习提示。
        </Text>
        <Button
          className='clip-insight__btn'
          loading={insightLoading}
          onClick={() => void handleGenerateInsight()}
        >
          {insight ? '重新生成解读' : '生成 AI 解读'}
        </Button>
        {insight ? (
          <Text className='clip-insight__insight'>{insight}</Text>
        ) : null}
      </View>
    </ScrollView>
  )
}

export default ClipInsightPage
