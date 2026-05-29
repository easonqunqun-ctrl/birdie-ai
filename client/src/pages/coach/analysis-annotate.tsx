/**
 * M12-09 · 教练在分析报告上引用职业镜头（video_ref）。
 */

import { FC, useCallback, useEffect, useState } from 'react'
import { View, Text, Button, ScrollView } from '@tarojs/components'
import Taro, { useRouter } from '@tarojs/taro'
import ProClipPicker from '@/components/ProClipPicker'
import '@/components/ProClipPicker.scss'
import ProClipReferenceCard from '@/components/ProClipReferenceCard'
import '@/components/ProClipReferenceCard.scss'
import { PHASE2_PROS_ENABLED_FLAG } from '@/constants/flags'
import {
  coachAnnotationService,
  type CoachAnnotationClipRef,
} from '@/services/coachAnnotationService'
import type { ProPlayerRead, ProSwingClipRead } from '@/services/prosService'
import { useUserStore } from '@/store/userStore'
import './analysis-annotate.scss'

const CoachAnalysisAnnotatePage: FC = () => {
  const router = useRouter()
  const analysisId = (router.params.analysisId || '').trim()
  const user = useUserStore((s) => s.user)
  const canCoach = Boolean(user?.can_coach_annotate)

  const [loading, setLoading] = useState(true)
  const [items, setItems] = useState<CoachAnnotationClipRef[]>([])
  const [pickerOpen, setPickerOpen] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  const load = useCallback(async () => {
    if (!analysisId) {
      setLoading(false)
      return
    }
    setLoading(true)
    try {
      const list = await coachAnnotationService.listCoach(analysisId)
      setItems(list)
    } catch (e) {
      Taro.showToast({
        title: e instanceof Error ? e.message : '加载失败',
        icon: 'none',
      })
    } finally {
      setLoading(false)
    }
  }, [analysisId])

  useEffect(() => {
    if (!canCoach || !PHASE2_PROS_ENABLED_FLAG) {
      setLoading(false)
      return
    }
    void load()
  }, [canCoach, load])

  const handleSelect = async (clip: ProSwingClipRead, _player: ProPlayerRead) => {
    if (!analysisId || submitting) return
    setSubmitting(true)
    try {
      await coachAnnotationService.createVideoRef(analysisId, {
        pro_clip_id: clip.id,
      })
      Taro.showToast({ title: '已添加参考', icon: 'success' })
      await load()
    } catch (e) {
      Taro.showToast({
        title: e instanceof Error ? e.message : '添加失败',
        icon: 'none',
      })
    } finally {
      setSubmitting(false)
    }
  }

  if (!canCoach || !PHASE2_PROS_ENABLED_FLAG) {
    return (
      <View className='coach-annotate coach-annotate--empty'>
        <Text>当前账号无教练批注权限</Text>
        <Button onClick={() => Taro.navigateBack().catch(() => undefined)}>返回</Button>
      </View>
    )
  }

  if (!analysisId) {
    return (
      <View className='coach-annotate coach-annotate--empty'>
        <Text>缺少分析报告 ID</Text>
      </View>
    )
  }

  return (
    <ScrollView scrollY className='coach-annotate'>
      <View className='coach-annotate__head'>
        <Text className='coach-annotate__title'>引用职业镜头</Text>
        <Text className='coach-annotate__meta'>报告 {analysisId.slice(0, 8)}…</Text>
      </View>
      <Text className='coach-annotate__hint'>
        为学员推荐可对标的职业挥杆参考；学员将在报告页看到缩略图，并可一键进入对比页。
      </Text>
      <Text className='coach-annotate__section-title'>已添加的参考</Text>
      {loading ? (
        <Text className='coach-annotate__empty-list'>加载中…</Text>
      ) : items.length === 0 ? (
        <Text className='coach-annotate__empty-list'>尚未引用职业镜头</Text>
      ) : (
        items.map((ann) => (
          <ProClipReferenceCard
            key={ann.id}
            annotation={ann}
            analysisId={analysisId}
          />
        ))
      )}
      <Button
        className='coach-annotate__add'
        loading={submitting}
        onClick={() => setPickerOpen(true)}
      >
        引用球手 clip
      </Button>
      <ProClipPicker
        visible={pickerOpen}
        onClose={() => setPickerOpen(false)}
        onSelect={(clip, player) => void handleSelect(clip, player)}
      />
    </ScrollView>
  )
}

export default CoachAnalysisAnnotatePage
