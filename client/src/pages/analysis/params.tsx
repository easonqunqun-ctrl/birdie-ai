/**
 * 分析参数页：选择拍摄角度 / 球杆 → 直传 MinIO → 创建任务 → 跳 waiting
 *
 * 上一步（capture）把 tempFilePath / size / duration 放在路由 query 里传入；
 * 任何一个必需参数缺失都直接回退到 capture 重选。
 *
 * 提交流程（串行，带 loading 遮罩防止二次点击）：
 *   getUploadToken -> uploadToMinio -> createAnalysis -> setCurrent(analysisId) -> redirectTo waiting
 * 任一步失败 toast + 解除 loading；已签发但没上传成功的凭证由后端 TTL 清理，前端无需处理。
 */

import { FC, useEffect, useMemo, useState } from 'react'
import { View, Text, Button, ScrollView } from '@tarojs/components'
import Taro, { useRouter } from '@tarojs/taro'
import { analysisService } from '@/services/analysisService'
import { useAnalysisStore } from '@/store/analysisStore'
import { useUserStore } from '@/store/userStore'
import {
  CAMERA_ANGLE_DESC,
  CAMERA_ANGLE_LABEL,
  CLUB_TYPE_GROUPS,
  CLUB_TYPE_LABEL,
  VIDEO_CONSTRAINTS,
} from '@/types/analysis'
import type { CameraAngle, ClubType } from '@/types/api'
import './params.scss'

const CAMERA_ANGLES: CameraAngle[] = ['face_on', 'down_the_line']

function formatSize(bytes: number): string {
  if (!bytes) return '-'
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)}KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`
}

function guessContentType(path: string): string {
  const ext = path.toLowerCase().split('?')[0].split('.').pop()
  if (ext === 'mov') return 'video/quicktime'
  return 'video/mp4'
}

/** 从 tempFilePath 里抠出一个合规的 file_name（后端会校验扩展名） */
function deriveFileName(path: string): string {
  const base = path.split('/').pop() || 'swing.mp4'
  const safe = base.replace(/[^\w.]/g, '_')
  if (!/\.(mp4|mov)$/i.test(safe)) return `${safe}.mp4`
  return safe
}

const AnalysisParamsPage: FC = () => {
  const router = useRouter()
  const query = router.params as {
    tempFilePath?: string
    size?: string
    duration?: string
  }

  const tempFilePath = query.tempFilePath ? decodeURIComponent(query.tempFilePath) : ''
  const size = Number(query.size || 0)
  const duration = Number(query.duration || 0)

  const [cameraAngle, setCameraAngle] = useState<CameraAngle>('face_on')
  const [clubType, setClubType] = useState<ClubType>('iron_7')
  const [submitting, setSubmitting] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [phase, setPhase] = useState<'idle' | 'signing' | 'uploading' | 'creating'>('idle')

  const setCurrent = useAnalysisStore((s) => s.setCurrent)
  const fetchMe = useUserStore((s) => s.fetchMe)

  // 必要参数缺失 → 直接回退到 capture
  useEffect(() => {
    if (!tempFilePath || !size || !duration) {
      Taro.showToast({ title: '视频信息缺失，请重新选择', icon: 'none' })
      setTimeout(() => Taro.redirectTo({ url: '/pages/analysis/capture' }), 800)
    }
  }, [tempFilePath, size, duration])

  const overLimit = useMemo(() => {
    if (size > VIDEO_CONSTRAINTS.MAX_SIZE_BYTES) return `文件过大：${formatSize(size)}`
    if (duration < VIDEO_CONSTRAINTS.MIN_DURATION_SECONDS) return `时长过短：${duration.toFixed(1)}s`
    if (duration > VIDEO_CONSTRAINTS.MAX_DURATION_SECONDS) return `时长过长：${duration.toFixed(1)}s`
    return null
  }, [size, duration])

  const handleStart = async () => {
    if (submitting) return
    if (overLimit) {
      Taro.showToast({ title: overLimit, icon: 'none' })
      return
    }
    setSubmitting(true)
    setPhase('signing')
    Taro.showLoading({ title: '申请上传凭证' })
    try {
      const contentType = guessContentType(tempFilePath)
      const token = await analysisService.getUploadToken({
        file_name: deriveFileName(tempFilePath),
        file_size: size,
        file_type: contentType,
        duration,
      })

      setPhase('uploading')
      Taro.showLoading({ title: '上传视频中 0%' })
      await analysisService.uploadToMinio(tempFilePath, token, {
        onProgress: (e) => {
          setUploadProgress(e.progress)
          Taro.showLoading({ title: `上传视频中 ${e.progress}%` })
        },
      })

      setPhase('creating')
      Taro.showLoading({ title: '创建分析任务' })
      const created = await analysisService.createAnalysis({
        upload_id: token.upload_id,
        camera_angle: cameraAngle,
        club_type: clubType,
      })

      Taro.hideLoading()
      setCurrent(created.analysis_id)

      // 刷新一下用户配额（创建成功后 analysis_remaining 会 -1）
      fetchMe().catch(() => undefined)

      Taro.redirectTo({ url: `/pages/analysis/waiting?id=${created.analysis_id}` })
    } catch (e) {
      Taro.hideLoading()
      const msg = (e as Error).message || '创建分析任务失败'
      Taro.showModal({
        title: '创建失败',
        content: msg,
        showCancel: false,
        confirmText: '我知道了',
      })
    } finally {
      setSubmitting(false)
      setPhase('idle')
      setUploadProgress(0)
    }
  }

  const disabled = submitting || !!overLimit

  return (
    <View className='params'>
      <View className='params__summary'>
        <Text className='params__summary-label'>已选视频</Text>
        <Text className='params__summary-meta'>
          {duration.toFixed(1)}s · {formatSize(size)}
        </Text>
        {overLimit && <Text className='params__summary-error'>⚠ {overLimit}</Text>}
      </View>

      <View className='params__section'>
        <Text className='params__section-title'>拍摄角度</Text>
        <Text className='params__section-hint'>正确的角度让分析更精准</Text>
        <View className='params__angle-grid'>
          {CAMERA_ANGLES.map((a) => {
            const active = cameraAngle === a
            return (
              <View
                key={a}
                className={`params__angle-card ${active ? 'params__angle-card--active' : ''}`}
                onClick={() => setCameraAngle(a)}
              >
                <Text className='params__angle-title'>{CAMERA_ANGLE_LABEL[a]}</Text>
                <Text className='params__angle-desc'>{CAMERA_ANGLE_DESC[a]}</Text>
              </View>
            )
          })}
        </View>
      </View>

      <View className='params__section'>
        <Text className='params__section-title'>使用的球杆</Text>
        <Text className='params__section-hint'>
          选一个最接近的，不确定可选&ldquo;其他&rdquo;
        </Text>
        <ScrollView scrollY className='params__club-scroll'>
          {CLUB_TYPE_GROUPS.map((group) => (
            <View key={group.title} className='params__club-group'>
              <Text className='params__club-group-title'>{group.title}</Text>
              <View className='params__club-grid'>
                {group.items.map((c) => {
                  const active = clubType === c
                  return (
                    <View
                      key={c}
                      className={`params__club-chip ${active ? 'params__club-chip--active' : ''}`}
                      onClick={() => setClubType(c)}
                    >
                      <Text>{CLUB_TYPE_LABEL[c]}</Text>
                    </View>
                  )
                })}
              </View>
            </View>
          ))}
        </ScrollView>
      </View>

      <View className='params__footer'>
        {phase === 'uploading' && (
          <View className='params__progress'>
            <View className='params__progress-bar'>
              <View
                className='params__progress-fill'
                style={{ width: `${uploadProgress}%` }}
              />
            </View>
            <Text className='params__progress-text'>上传中 {uploadProgress}%</Text>
          </View>
        )}
        <Button
          className={`params__submit ${disabled ? 'params__submit--disabled' : ''}`}
          disabled={disabled}
          loading={submitting}
          onClick={handleStart}
        >
          {submitting ? '处理中…' : '开始分析'}
        </Button>
      </View>
    </View>
  )
}

export default AnalysisParamsPage
