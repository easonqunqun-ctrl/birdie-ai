/**
 * M7-13 · 多挥视频选段：展示候选列表，确认后创建分析任务。
 */

import { FC, useEffect, useMemo, useState } from 'react'
import { View, Text, Button, Image } from '@tarojs/components'
import Taro, { useRouter } from '@tarojs/taro'
import { analysisService } from '@/services/analysisService'
import { describeIntermittentRequestFailure, isRequestError } from '@/services/request'
import { useAnalysisStore } from '@/store/analysisStore'
import { useUserStore } from '@/store/userStore'
import { track } from '@/utils/track'
import type { SwingCandidateItem } from '@/types/analysis'
import { sanitizeSwingCandidates } from '@/utils/sanitizeSwingCandidates'
import './select-swing.scss'

function formatTimeSec(sec: number): string {
  const safe = Math.max(0, sec)
  // 不足 10 秒用一位小数，避免 0.3s 被显示成「0:00」误导用户
  if (safe < 10) {
    return `${safe.toFixed(1)}s`
  }
  const total = Math.floor(safe)
  const m = Math.floor(total / 60)
  const s = total % 60
  return `${m}:${String(s).padStart(2, '0')}`
}

function formatCandidateRange(item: SwingCandidateItem): string {
  return `${formatTimeSec(item.start_time_sec)} – ${formatTimeSec(item.end_time_sec)}`
}

const SelectSwingPage: FC = () => {
  const router = useRouter()
  const uploadId = router.params.uploadId ? decodeURIComponent(router.params.uploadId) : ''

  const pending = useAnalysisStore((s) => s.pendingSwingSelection)
  const clearPending = useAnalysisStore((s) => s.clearPendingSwingSelection)
  const setCurrent = useAnalysisStore((s) => s.setCurrent)
  const fetchMe = useUserStore((s) => s.fetchMe)

  const [selectedIndex, setSelectedIndex] = useState(0)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (!uploadId || !pending || pending.uploadId !== uploadId) {
      Taro.showToast({ title: '选段信息已失效，请重新上传', icon: 'none' })
      setTimeout(() => Taro.redirectTo({ url: '/pages/analysis/capture' }), 800)
      return
    }
    const sanitized = sanitizeSwingCandidates(
      pending.swingCandidates,
      pending.defaultSelectedIndex,
    )
    setSelectedIndex(sanitized.default_selected_index)
  }, [uploadId, pending])

  const candidates = useMemo(() => {
    const raw = pending?.swingCandidates ?? []
    if (!pending) return []
    return sanitizeSwingCandidates(raw, pending.defaultSelectedIndex).swing_candidates
  }, [pending])

  const selectedItem = useMemo(
    () => candidates[selectedIndex] ?? null,
    [candidates, selectedIndex],
  )

  const handleConfirm = async () => {
    if (!pending || submitting || !selectedItem) return
    setSubmitting(true)
    try {
      Taro.showLoading({ title: '创建分析任务' })
      const created = await analysisService.createAnalysis({
        upload_id: pending.uploadId,
        camera_angle: pending.cameraAngle,
        club_type: pending.clubType,
        mode: pending.mode,
        selected_swing_index: selectedIndex,
        ...(pending.targetYardage != null ? { target_yardage: pending.targetYardage } : {}),
      })
      Taro.hideLoading()
      clearPending()
      setCurrent(created.analysis_id)
      track('analysis_submit', {
        analysis_id: created.analysis_id,
        club_type: pending.clubType,
        camera_angle: pending.cameraAngle,
        analysis_mode: pending.mode,
        duration: pending.duration,
        size: pending.size,
        selected_swing_index: selectedIndex,
        multi_swing: true,
      })
      fetchMe().catch(() => undefined)
      Taro.redirectTo({ url: `/pages/analysis/waiting?id=${created.analysis_id}` })
    } catch (e) {
      Taro.hideLoading()
      let msg =
        isRequestError(e) && typeof e.message === 'string' && e.message.trim()
          ? e.message.trim()
          : ''
      if (!msg) msg = describeIntermittentRequestFailure(e).toastTitle
      Taro.showModal({
        title: '创建失败',
        content: msg.length > 220 ? `${msg.slice(0, 217)}…` : msg,
        showCancel: false,
        confirmText: '我知道了',
      })
    } finally {
      setSubmitting(false)
    }
  }

  if (!pending || pending.uploadId !== uploadId) {
    return <View className='select-swing' />
  }

  return (
    <View className='select-swing'>
      <View className='select-swing__intro'>
        <Text className='select-swing__intro-title'>
          检测到 {candidates.length} 段挥杆
        </Text>
        <Text className='select-swing__intro-hint'>
          请选择要分析的一段。试挥段已标注，默认选中第一段正式挥杆。
        </Text>
      </View>

      <View className='select-swing__list'>
        {candidates.map((item, index) => {
          const active = selectedIndex === index
          return (
            <View
              key={`${item.start_frame}-${item.end_frame}`}
              className={`select-swing__item ${active ? 'select-swing__item--active' : ''}`}
              onClick={() => setSelectedIndex(index)}
            >
              <View className='select-swing__item-body'>
                {item.preview_frame_url ? (
                  <Image
                    mode='aspectFill'
                    src={item.preview_frame_url}
                    className='select-swing__thumb'
                  />
                ) : (
                  <View className='select-swing__thumb select-swing__thumb--placeholder'>
                    <Text className='select-swing__thumb-label'>{index + 1}</Text>
                  </View>
                )}
                <View className='select-swing__item-content'>
                  <View className='select-swing__item-row'>
                    <Text className='select-swing__item-title'>第 {index + 1} 段</Text>
                    <Text
                      className={`select-swing__badge ${
                        item.is_practice
                          ? 'select-swing__badge--practice'
                          : 'select-swing__badge--formal'
                      }`}
                    >
                      {item.is_practice ? '试挥' : '正式'}
                    </Text>
                  </View>
                  <Text className='select-swing__item-time'>{formatCandidateRange(item)}</Text>
                </View>
              </View>
            </View>
          )
        })}
      </View>

      <View className='select-swing__footer'>
        <Button
          className={`select-swing__submit ${submitting ? 'select-swing__submit--disabled' : ''}`}
          disabled={submitting || !selectedItem}
          loading={submitting}
          onClick={handleConfirm}
        >
          {submitting ? '处理中…' : '分析所选段'}
        </Button>
      </View>
    </View>
  )
}

export default SelectSwingPage
