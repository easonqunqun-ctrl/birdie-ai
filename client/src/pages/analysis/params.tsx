/**
 * 分析参数页：选择拍摄角度 / 球杆 → 直传 MinIO → 创建任务 → 跳 waiting
 *
 * 上一步（capture）把 tempFilePath / size / duration 放在路由 query 里传入；
 * 任何一个必需参数缺失都直接回退到 capture 重选。
 *
 * 提交流程（串行，带 loading 遮罩防止二次点击）：
 *   getUploadToken -> uploadVideoViaApi（同源 POST multipart）-> createAnalysis -> setCurrent(analysisId) -> redirectTo waiting
 * 任一步失败 toast + 解除 loading；已签发但没上传成功的凭证由后端 TTL 清理，前端无需处理。
 */

import { FC, useEffect, useMemo, useState } from 'react'
import { View, Text, Button, ScrollView } from '@tarojs/components'
import Taro, { useRouter } from '@tarojs/taro'
import { analysisService, uploadLikelyNeedsFreshToken } from '@/services/analysisService'
import { checkVideoFirstFrame } from '@/services/mediaCheck'
import { describeIntermittentRequestFailure, isRequestError } from '@/services/request'
import {
  confirmQualityWarningsIfNeeded,
  precheckVideoQuality,
  showQualityBlockModal,
} from '@/services/videoQualityPrecheck'
import { linesForQualityBlocks } from '@/constants/qualityBlockers'
import { linesForQualityWarnings } from '@/constants/qualityWarnings'
import { useAnalysisStore } from '@/store/analysisStore'
import { useUserStore } from '@/store/userStore'
import { track } from '@/utils/track'
import {
  CAMERA_ANGLE_DESC,
  CAMERA_ANGLE_LABEL,
  CLUB_TYPE_GROUPS,
  CLUB_TYPE_LABEL,
  VIDEO_CONSTRAINTS,
} from '@/types/analysis'
import type { AnalysisMode } from '@/types/analysis'
import type { CameraAngle, ClubType } from '@/types/api'
import { PHASE2_CHIPPING_MODE_ENABLED_FLAG, PHASE2_PUTTING_MODE_ENABLED_FLAG } from '@/constants/flags'
import ModeSelector from '@/components/ModeSelector'
import '@/components/ModeSelector.scss'
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
    thumbTempFilePath?: string
  }

  const tempFilePath = query.tempFilePath ? decodeURIComponent(query.tempFilePath) : ''
  const size = Number(query.size || 0)
  const duration = Number(query.duration || 0)
  // W8-T5：视频首帧路径（weapp chooseMedia 返回）；RN / 部分机型可能为空
  const thumbTempFilePath = query.thumbTempFilePath
    ? decodeURIComponent(query.thumbTempFilePath)
    : ''

  const [cameraAngle, setCameraAngle] = useState<CameraAngle>('face_on')
  const [clubType, setClubType] = useState<ClubType>('iron_7')
  const [analysisMode, setAnalysisMode] = useState<AnalysisMode>('full_swing')
  const [submitting, setSubmitting] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [phase, setPhase] = useState<
    'idle' | 'quality' | 'checking' | 'signing' | 'uploading' | 'creating'
  >('idle')
  const [qualityWarnings, setQualityWarnings] = useState<string[]>([])
  const [qualityBlocks, setQualityBlocks] = useState<string[]>([])
  const [qualityChecking, setQualityChecking] = useState(false)

  const setCurrent = useAnalysisStore((s) => s.setCurrent)
  const fetchMe = useUserStore((s) => s.fetchMe)

  const modeOptions = useMemo(
    () => [
      { value: 'full_swing' as const, label: '全挥杆', icon: '⛳' },
      {
        value: 'putting' as const,
        label: '推杆',
        icon: '🎯',
        disabled: !PHASE2_PUTTING_MODE_ENABLED_FLAG,
        hint: PHASE2_PUTTING_MODE_ENABLED_FLAG ? '建议正面拍摄' : '即将开放',
      },
      {
        value: 'chipping' as const,
        label: '切杆',
        icon: '🏌️',
        disabled: !PHASE2_CHIPPING_MODE_ENABLED_FLAG,
        hint: PHASE2_CHIPPING_MODE_ENABLED_FLAG ? '建议选挖起杆' : '即将开放',
      },
    ],
    [],
  )

  const showModeSelector =
    PHASE2_PUTTING_MODE_ENABLED_FLAG || PHASE2_CHIPPING_MODE_ENABLED_FLAG

  useEffect(() => {
    if (analysisMode === 'putting' && clubType !== 'putter') {
      Taro.showModal({
        title: '提示',
        content: '推杆模式建议选择推杆（putter）',
        showCancel: false,
        confirmText: '我知道了',
      })
    }
  }, [analysisMode, clubType])

  useEffect(() => {
    if (analysisMode === 'putting') {
      setClubType('putter')
      setCameraAngle('face_on')
    } else if (analysisMode === 'chipping' && clubType === 'putter') {
      setClubType('wedge')
    }
  }, [analysisMode])

  // 必要参数缺失 → 直接回退到 capture
  useEffect(() => {
    if (!tempFilePath || !size || !duration) {
      Taro.showToast({ title: '视频信息缺失，请重新选择', icon: 'none' })
      setTimeout(() => Taro.redirectTo({ url: '/pages/analysis/capture' }), 800)
    }
  }, [tempFilePath, size, duration])

  // O-08 子集：首帧缩略图亮度/清晰度启发式（无缩略图则跳过）
  useEffect(() => {
    if (!thumbTempFilePath) {
      setQualityWarnings([])
      setQualityBlocks([])
      setQualityChecking(false)
      return
    }
    let cancelled = false
    setQualityChecking(true)
    precheckVideoQuality({
      thumbTempFilePath,
      videoTempFilePath: tempFilePath,
      durationSec: duration,
    })
      .then((r) => {
        if (!cancelled) {
          setQualityBlocks(r.blocks)
          setQualityWarnings(r.warnings)
        }
      })
      .finally(() => {
        if (!cancelled) setQualityChecking(false)
      })
    return () => {
      cancelled = true
    }
  }, [thumbTempFilePath, tempFilePath, duration])

  const qualityHintLines = useMemo(
    () => linesForQualityWarnings(qualityWarnings),
    [qualityWarnings],
  )

  const qualityBlockLines = useMemo(
    () => linesForQualityBlocks(qualityBlocks),
    [qualityBlocks],
  )

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
    try {
      setPhase('quality')
      let blockCodes = qualityBlocks
      let warnCodes = qualityWarnings
      if (!blockCodes.length && !warnCodes.length && thumbTempFilePath) {
        Taro.showLoading({ title: '检查拍摄质量' })
        const pre = await precheckVideoQuality({
          thumbTempFilePath,
          videoTempFilePath: tempFilePath,
          durationSec: duration,
        })
        blockCodes = pre.blocks
        warnCodes = pre.warnings
        setQualityBlocks(pre.blocks)
        setQualityWarnings(pre.warnings)
        Taro.hideLoading()
      }
      if (blockCodes.length) {
        await showQualityBlockModal(blockCodes)
        Taro.redirectTo({ url: '/pages/analysis/capture' })
        return
      }
      if (warnCodes.length) {
        const proceed = await confirmQualityWarningsIfNeeded(warnCodes)
        if (!proceed) {
          Taro.redirectTo({ url: '/pages/analysis/capture' })
          return
        }
      }

      // W8-T5：上传视频前先走一遍微信 imgSecCheck（首帧合规预检）。
      //   - 只有真的拒绝（passed=false）才 abort；fail-open 场景照常上传。
      //   - 没 thumbTempFilePath 的端（RN / 老机型）会被 checkVideoFirstFrame 直接返回 passed=true。
      if (thumbTempFilePath) {
        setPhase('checking')
        Taro.showLoading({ title: '内容审核中' })
        const check = await checkVideoFirstFrame(thumbTempFilePath, 'analysis')
        if (!check.passed) {
          Taro.hideLoading()
          Taro.showModal({
            title: '内容审核未通过',
            content: check.reason || '视频内容涉嫌违规，请更换视频',
            showCancel: false,
            confirmText: '我知道了',
          })
          return
        }
      }

      setPhase('signing')
      Taro.showLoading({ title: '申请上传凭证' })
      const contentType = guessContentType(tempFilePath)
      const tokenPayload = {
        file_name: deriveFileName(tempFilePath),
        file_size: size,
        file_type: contentType,
        duration,
      }
      let token = await analysisService.getUploadToken(tokenPayload)

      setPhase('uploading')
      Taro.showLoading({ title: '上传视频中 0%' })
      const progressOpts = {
        onProgress: (e: { progress: number }) => {
          setUploadProgress(e.progress)
          Taro.showLoading({ title: `上传视频中 ${e.progress}%` })
        },
      }
      try {
        await analysisService.uploadToMinio(tempFilePath, token, progressOpts)
      } catch (uploadErr) {
        const raw =
          uploadErr instanceof Error ? uploadErr.message : String(uploadErr)
        if (!uploadLikelyNeedsFreshToken(raw)) {
          throw uploadErr instanceof Error ? uploadErr : new Error(raw)
        }
        Taro.showLoading({ title: '刷新凭证并重试上传' })
        token = await analysisService.getUploadToken(tokenPayload)
        await analysisService.uploadToMinio(tempFilePath, token, progressOpts)
      }

      setPhase('creating')
      Taro.showLoading({ title: '创建分析任务' })
      const created = await analysisService.createAnalysis({
        upload_id: token.upload_id,
        camera_angle: cameraAngle,
        club_type: clubType,
        mode: analysisMode,
      })

      Taro.hideLoading()
      setCurrent(created.analysis_id)

      // W8-T5：核心闭环埋点 — 用户成功提交一次分析任务
      track('analysis_submit', {
        analysis_id: created.analysis_id,
        club_type: clubType,
        camera_angle: cameraAngle,
        analysis_mode: analysisMode,
        duration,
        size,
      })

      // 刷新一下用户配额（创建成功后 analysis_remaining 会 -1）
      fetchMe().catch(() => undefined)

      Taro.redirectTo({ url: `/pages/analysis/waiting?id=${created.analysis_id}` })
    } catch (e) {
      Taro.hideLoading()
      let msg =
        isRequestError(e) && typeof e.message === 'string' && e.message.trim()
          ? e.message.trim()
          : ''
      const traceId =
        isRequestError(e) &&
        typeof e.requestId === 'string' &&
        e.requestId.trim()
          ? e.requestId.trim()
          : ''
      if (
        !msg &&
        typeof e === 'object' &&
        e &&
        'message' in e &&
        typeof (e as Error).message === 'string'
      ) {
        msg = ((e as Error).message || '').trim()
      }
      if (!msg) msg = describeIntermittentRequestFailure(e).toastTitle
      let body = msg.length > 220 ? `${msg.slice(0, 217)}…` : msg
      if (traceId) body += `\n\n追踪 ID：${traceId}`
      Taro.showModal({
        title: '创建失败',
        content: body,
        showCancel: false,
        confirmText: '我知道了',
      })
    } finally {
      setSubmitting(false)
      setPhase('idle')
      setUploadProgress(0)
    }
  }

  const disabled = submitting || !!overLimit || qualityBlocks.length > 0

  return (
    <View className='params'>
      <View className='params__summary'>
        <Text className='params__summary-label'>已选视频</Text>
        <Text className='params__summary-meta'>
          {duration.toFixed(1)}s · {formatSize(size)}
        </Text>
        {overLimit && <Text className='params__summary-error'>⚠ {overLimit}</Text>}
        {qualityChecking && (
          <Text className='params__summary-hint'>正在检查拍摄质量（5 秒内）…</Text>
        )}
        {!qualityChecking && qualityBlockLines.length > 0 && (
          <View className='params__quality-block'>
            <Text className='params__quality-block-title'>无法开始分析</Text>
            {qualityBlockLines.map((line) => (
              <Text key={line} className='params__quality-block-line'>
                {line}
              </Text>
            ))}
            <Text className='params__quality-block-foot'>请返回重新拍摄后再试。</Text>
          </View>
        )}
        {!qualityChecking && qualityBlockLines.length === 0 && qualityHintLines.length > 0 && (
          <View className='params__quality-warn'>
            <Text className='params__quality-warn-title'>拍摄质量提示</Text>
            {qualityHintLines.map((line) => (
              <Text key={line} className='params__quality-warn-line'>
                {line}
              </Text>
            ))}
            <Text className='params__quality-warn-foot'>
              可继续上传，分析报告会再次提示；建议改善后重拍。
            </Text>
          </View>
        )}
      </View>

      {showModeSelector && (
        <View className='params__section'>
          <Text className='params__section-title'>分析模式</Text>
          <Text className='params__section-hint'>
            推杆请选推杆球杆并尽量正面拍摄
          </Text>
          <ModeSelector
            value={analysisMode}
            options={modeOptions}
            onChange={setAnalysisMode}
          />
        </View>
      )}

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
