/**
 * M8-04 / M12-09 · 教练在分析报告上添加文字批注与引用职业镜头。
 */

import { FC, useCallback, useEffect, useMemo, useState } from 'react'
import { View, Text, Button, ScrollView, Textarea } from '@tarojs/components'
import Taro, { useRouter } from '@tarojs/taro'
import CoachTextAnnotationCard from '@/components/CoachTextAnnotationCard'
import '@/components/CoachTextAnnotationCard.scss'
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
  const canCoach = Boolean(user?.can_coach_annotate || user?.is_active_coach)

  const [loading, setLoading] = useState(true)
  const [items, setItems] = useState<CoachAnnotationClipRef[]>([])
  const [pickerOpen, setPickerOpen] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [textDraft, setTextDraft] = useState('')

  const textItems = useMemo(
    () => items.filter((item) => item.annotation_type === 'text'),
    [items],
  )
  const clipItems = useMemo(
    () => items.filter((item) => item.annotation_type === 'video_ref'),
    [items],
  )

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
    if (!canCoach) {
      setLoading(false)
      return
    }
    void load()
  }, [canCoach, load])

  const handleSelect = async (clip: ProSwingClipRead, _player: ProPlayerRead) => {
    if (!analysisId || submitting || !PHASE2_PROS_ENABLED_FLAG) return
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

  const handleSubmitText = async () => {
    const text = textDraft.trim()
    if (!analysisId || submitting || !text) {
      Taro.showToast({ title: '请输入文字批注', icon: 'none' })
      return
    }
    setSubmitting(true)
    try {
      await coachAnnotationService.createText(analysisId, { text_content: text })
      setTextDraft('')
      Taro.showToast({ title: '已发送点评', icon: 'success' })
      await load()
    } catch (e) {
      Taro.showToast({
        title: e instanceof Error ? e.message : '发送失败',
        icon: 'none',
      })
    } finally {
      setSubmitting(false)
    }
  }

  if (!canCoach) {
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
        <Text className='coach-annotate__title'>报告批注</Text>
        <Text className='coach-annotate__meta'>报告 {analysisId.slice(0, 8)}…</Text>
      </View>
      <Text className='coach-annotate__hint'>
        仅 active 师生关系下的学员报告可批注；学员将在报告页看到已发送的内容。
      </Text>

      <Text className='coach-annotate__section-title'>文字点评</Text>
      <Textarea
        className='coach-annotate__textarea'
        value={textDraft}
        maxlength={500}
        placeholder='写下对本杆的具体建议（最多 500 字）'
        onInput={(e) => setTextDraft(String(e.detail.value || ''))}
      />
      <Button
        className='coach-annotate__submit-text'
        loading={submitting}
        onClick={() => void handleSubmitText()}
      >
        发送文字批注
      </Button>

      {loading ? (
        <Text className='coach-annotate__empty-list'>加载中…</Text>
      ) : textItems.length === 0 ? (
        <Text className='coach-annotate__empty-list'>尚无文字批注</Text>
      ) : (
        textItems.map((ann) => <CoachTextAnnotationCard key={ann.id} annotation={ann} />)
      )}

      {PHASE2_PROS_ENABLED_FLAG ? (
        <>
          <Text className='coach-annotate__section-title coach-annotate__section-title--spaced'>
            职业镜头参考
          </Text>
          <Text className='coach-annotate__hint'>
            为学员推荐可对标的职业挥杆参考；学员可在报告页一键进入对比页。
          </Text>
          {clipItems.length === 0 ? (
            <Text className='coach-annotate__empty-list'>尚未引用职业镜头</Text>
          ) : (
            clipItems.map((ann) => (
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
        </>
      ) : null}
    </ScrollView>
  )
}

export default CoachAnalysisAnnotatePage
