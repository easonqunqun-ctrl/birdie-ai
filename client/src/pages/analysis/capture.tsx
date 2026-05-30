/**
 * 拍摄引导页（MVP §4.1）
 *
 * 职责：
 * 1. 告诉用户合规的拍摄要点（3 条 tips + 正/侧示意）
 * 2. 拉起微信 chooseMedia：可直接拍摄也可从相册选
 * 3. 前端先做一层硬约束（时长 / 大小 / 扩展名）过滤掉明显不合规的视频
 * 4. 合规后跳转 params 页，把 `tempFilePath / duration / size / fileType` 通过 URL 带过去
 *
 * 首次进入会按 `storage.hasSeenAnalysisGuide()` 判断是否显示"新手提示"顶栏；
 * 用户点任一 CTA 后即标记已看过，后续只保留简洁 tips。
 */

import { FC, useEffect, useState } from 'react'
import { View, Text, Button } from '@tarojs/components'
import Taro from '@tarojs/taro'
import { chooseVideo } from '@/adapters/media'
import { describeIntermittentRequestFailure } from '@/services/request'
import { storage } from '@/utils/storage'
import { VIDEO_CONSTRAINTS } from '@/types/analysis'
import './capture.scss'

type MediaSource = 'camera' | 'album'

interface ChosenVideo {
  tempFilePath: string
  size: number
  duration: number
  /** 视频首帧缩略图路径（weapp 原生字段；W8-T5 用于合规预检） */
  thumbTempFilePath?: string
}

/**
 * 从文件名 / tempFilePath 推出扩展名；小程序里 tempFilePath 一般长这样：
 *   wxfile://tmp_xxx.mp4 或 http://tmp/xxx.MOV
 */
function extractExt(path: string): string {
  const dotIdx = path.lastIndexOf('.')
  if (dotIdx === -1) return ''
  return path.slice(dotIdx + 1).toLowerCase().split('?')[0]
}

/** 把字节转成人类可读，仅用于 toast */
function formatSize(bytes: number): string {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)}KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`
}

const TIPS = [
  { icon: '📐', text: '将球员放在画面中央，脚到头部全部露出' },
  { icon: '🎬', text: '拍 2-30 秒，建议只录 1 次完整挥杆' },
  { icon: '💡', text: '优选自然光，避免强背光和严重抖动' },
]

const CaptureAnalysisPage: FC = () => {
  const [showGuide, setShowGuide] = useState(false)

  useEffect(() => {
    setShowGuide(!storage.hasSeenAnalysisGuide())
  }, [])

  const handleChoose = async (source: MediaSource) => {
    try {
      // weapp：`chooseVideo` → Taro.chooseMedia + 隐私授权；RN：`react-native-image-picker`
      const raw = await chooseVideo({
        source,
        maxDurationSeconds: VIDEO_CONSTRAINTS.MAX_DURATION_SECONDS,
      })
      const picked: ChosenVideo = {
        tempFilePath: raw.filePath,
        size: raw.size,
        duration: raw.duration,
        thumbTempFilePath: raw.thumbTempFilePath,
      }
      const err = validateVideo(picked, raw.filePath)
      if (err) {
        Taro.showToast({ title: err, icon: 'none', duration: 2500 })
        return
      }

      storage.markAnalysisGuideSeen()

      // 通过 URL 传参；tempFilePath 一般很短，但稳妥起见做 encode
      // W8-T5：thumbTempFilePath 可为空（RN / 部分机型）；下一页按存在与否决定是否做合规预检
      const thumbParam = picked.thumbTempFilePath
        ? `&thumbTempFilePath=${encodeURIComponent(picked.thumbTempFilePath)}`
        : ''
      Taro.navigateTo({
        url:
          `/pages/analysis/params?tempFilePath=${encodeURIComponent(picked.tempFilePath)}` +
          `&size=${picked.size}` +
          `&duration=${picked.duration.toFixed(2)}` +
          `&source=${source}` +
          thumbParam,
      })
    } catch (e: unknown) {
      const err = e as { errMsg?: string; message?: string }
      const msg = err.errMsg || err.message || ''
      if (/cancel/i.test(msg) || /已取消/i.test(msg)) return
      const intermittent = describeIntermittentRequestFailure(e).toastTitle
      const title =
        msg.trim().length > 0 ? msg.trim() : intermittent.length > 0 ? intermittent : '操作未完成，请稍后重试'
      Taro.showToast({
        title: title.length > 120 ? `${title.slice(0, 119)}…` : title,
        icon: 'none',
      })
    }
  }

  return (
    <View className='capture'>
      {showGuide && (
        <View className='capture__banner'>
          <Text className='capture__banner-title'>第一次拍摄？先看看要点 👇</Text>
          <Text className='capture__banner-sub'>拍得好 = 分析更准</Text>
        </View>
      )}

      <View className='capture__hero'>
        <View className='capture__hero-figure'>
          <View className='capture__hero-guide'>
            <View className='capture__hero-crop'>
              <Text className='capture__hero-icon'>🏌️</Text>
            </View>
          </View>
          <Text className='capture__hero-hint'>
            对准人物
            {'\n'}
            居中入画
          </Text>
        </View>
      </View>

      <View className='capture__tips'>
        {TIPS.map((t) => (
          <View key={t.text} className='capture__tip'>
            <Text className='capture__tip-icon'>{t.icon}</Text>
            <Text className='capture__tip-text'>{t.text}</Text>
          </View>
        ))}
      </View>

      <View className='capture__actions'>
        <Button className='capture__btn capture__btn--primary' onClick={() => handleChoose('camera')}>
          📷 立即拍摄
        </Button>
        <Button className='capture__btn capture__btn--ghost' onClick={() => handleChoose('album')}>
          从相册选择
        </Button>
        <Text className='capture__hint'>
          时长 {VIDEO_CONSTRAINTS.MIN_DURATION_SECONDS}-{VIDEO_CONSTRAINTS.MAX_DURATION_SECONDS}s ·
          {'  '}
          大小 ≤ {Math.round(VIDEO_CONSTRAINTS.MAX_SIZE_BYTES / 1024 / 1024)}MB · 支持
          {'  '}
          {VIDEO_CONSTRAINTS.ACCEPTED_EXTENSIONS.join(' / ').toUpperCase()}
        </Text>
      </View>
    </View>
  )
}

/** 返回 null 表示合规；返回字符串是面向用户的错误提示 */
function validateVideo(v: ChosenVideo, originalPath: string): string | null {
  const { MIN_DURATION_SECONDS, MAX_DURATION_SECONDS, MAX_SIZE_BYTES, ACCEPTED_EXTENSIONS } =
    VIDEO_CONSTRAINTS

  if (v.duration < MIN_DURATION_SECONDS) {
    return `视频太短（${v.duration.toFixed(1)}s），至少需要 ${MIN_DURATION_SECONDS}s`
  }
  if (v.duration > MAX_DURATION_SECONDS) {
    return `视频太长（${v.duration.toFixed(1)}s），最多 ${MAX_DURATION_SECONDS}s`
  }
  if (v.size > MAX_SIZE_BYTES) {
    return `文件过大（${formatSize(v.size)}），限 ${Math.round(MAX_SIZE_BYTES / 1024 / 1024)}MB 以内`
  }
  const ext = extractExt(originalPath)
  // 相册来源的部分机型 tempFilePath 可能带奇怪后缀；允许 ext 为空时放行，由后端兜底拒绝
  if (ext && !ACCEPTED_EXTENSIONS.includes(ext as (typeof ACCEPTED_EXTENSIONS)[number])) {
    return `暂不支持 .${ext} 格式，请选择 ${ACCEPTED_EXTENSIONS.join('/').toUpperCase()}`
  }
  return null
}

export default CaptureAnalysisPage
