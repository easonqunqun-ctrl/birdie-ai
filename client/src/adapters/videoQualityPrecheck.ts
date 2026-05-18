import type { VideoQualityPrecheckResult } from '@/utils/videoQualityPrecheck'

export type { VideoQualityPrecheckResult } from '@/utils/videoQualityPrecheck'

/**
 * 上传前质量预检（O-08 子集）：当前以首帧缩略图启发式为主；无图则 fail-open。
 */
export async function precheckVideoQuality(input: {
  thumbTempFilePath?: string
  videoTempFilePath?: string
  durationSec?: number
}): Promise<VideoQualityPrecheckResult> {
  if (process.env.TARO_ENV === 'weapp') {
    const { precheckVideoQualityWeapp } = await import('./videoQualityPrecheck.weapp')
    return precheckVideoQualityWeapp({
      thumbTempFilePath: input.thumbTempFilePath,
      videoTempFilePath: input.videoTempFilePath,
      durationSec: input.durationSec,
    })
  }
  return { warnings: [], skipped: true, reason: 'unsupported_platform' }
}
