/**
 * 拍摄引导页（MVP §4.1）
 *
 * 职责：
 * 1. 告诉用户合规的拍摄要点（3 条 tips）
 * 2. 拉起微信 chooseMedia：可直接拍摄也可从相册选
 * 3. 前端先做一层硬约束（时长 / 大小 / 扩展名）过滤掉明显不合规的视频
 * 4. 合规后跳转 params 页，把 `tempFilePath / duration / size / fileType` 通过 URL 带过去
 *
 * 首次进入会按 `storage.hasSeenAnalysisGuide()` 判断是否显示"新手提示"顶栏；
 * 用户点任一 CTA 后即标记已看过，后续只保留简洁 tips。
 */

import { FC, useEffect, useMemo, useState } from 'react'
import { View, Text, Button } from '@tarojs/components'
import Taro from '@tarojs/taro'
import {
  chooseVideo,
  getCapturePlatformTips,
  summarizeChosenVideo,
} from '@/adapters/media'
import { describeIntermittentRequestFailure } from '@/services/request'
import { storage } from '@/utils/storage'
import { VIDEO_CONSTRAINTS } from '@/types/analysis'
import { validatePickedVideo } from '@/utils/videoPickNormalize'
import './capture.scss'

type MediaSource = 'camera' | 'album'

const BASE_TIPS = [
  { icon: '📐', text: '将球员放在画面中央，脚到头部全部露出' },
  { icon: '🎬', text: '拍满至少 2 秒（建议 3–5 秒），只录 1 次完整挥杆' },
  { icon: '💡', text: '优选自然光，避免强背光和严重抖动' },
]

const CaptureAnalysisPage: FC = () => {
  const [showGuide, setShowGuide] = useState(false)
  const tips = useMemo(() => {
    const extra = getCapturePlatformTips().map((text) => ({ icon: '📱', text }))
    return [...BASE_TIPS, ...extra]
  }, [])

  useEffect(() => {
    setShowGuide(!storage.hasSeenAnalysisGuide())
  }, [])

  const handleChoose = async (source: MediaSource) => {
    try {
      // weapp：`chooseVideo` → Taro.chooseMedia；RN：image-picker（差异仅在 adapter）
      const raw = await chooseVideo({
        source,
        maxDurationSeconds: VIDEO_CONSTRAINTS.MAX_DURATION_SECONDS,
        // App 相机臂：高质量 best-effort；相册臂用于系统慢动作导入（SP-1）
        preset: source === 'camera' ? 'high_quality' : 'standard',
      })
      const err = validatePickedVideo({
        filePath: raw.filePath,
        size: raw.size,
        duration: raw.duration,
      })
      if (err) {
        Taro.showToast({ title: err, icon: 'none', duration: 2500 })
        return
      }

      storage.markAnalysisGuideSeen()
      // SP-1：Metro / 远程调试可搜 SP1-pick，对照探针表
      console.info('[SP1-pick]', summarizeChosenVideo(source, raw))

      const thumbParam = raw.thumbTempFilePath
        ? `&thumbTempFilePath=${encodeURIComponent(raw.thumbTempFilePath)}`
        : ''
      Taro.navigateTo({
        url:
          `/pages/analysis/params?tempFilePath=${encodeURIComponent(raw.filePath)}` +
          `&size=${raw.size}` +
          `&duration=${raw.duration.toFixed(2)}` +
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
        {tips.map((t) => (
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

export default CaptureAnalysisPage
