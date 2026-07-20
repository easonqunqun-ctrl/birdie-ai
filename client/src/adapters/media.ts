/**
 * 视频拍摄/选择 adapter（微信小程序：Taro.chooseMedia）。
 *
 * 页面禁止写 `TARO_ENV === 'weapp'`；差异只进本文件（AGENTS §4）。
 * （原 React Native 分支已移除，App 端改用独立 Flutter 工程。）
 */

import Taro from '@tarojs/taro'
import { ensurePrivacyAuthorized } from '@/utils/privacy'
import {
  type CapturePresetId,
  formatVideoPickSummary,
} from '@/utils/videoPickNormalize'

export type { CapturePresetId }
export { CAPTURE_PRESET_LABEL, formatVideoPickSummary } from '@/utils/videoPickNormalize'

export interface ChosenVideo {
  filePath: string
  size: number
  duration: number
  width: number
  height: number
  /**
   * 视频首帧缩略图（仅 weapp 有；RN 需自行截帧）。
   * W8-T5：上传前会把这张图上送后端 `/v1/security/media-check`
   * 做微信内容合规预检（imgSecCheck）。
   */
  thumbTempFilePath?: string
  /** 本次选用的拍摄预设（RN；weapp 忽略） */
  preset?: CapturePresetId
}

export interface ChooseVideoOptions {
  source?: 'camera' | 'album' | 'both'
  maxDurationSeconds?: number
  /**
   * App 拍摄预设。相册导入时仅作记录；相机路径会映射 `videoQuality`。
   * 真正 120/240fps 需系统慢动作导入或后续原生模块（见 SP-1 runbook）。
   */
  preset?: CapturePresetId
}

/** 拍摄页平台 tip（小程序无追加 tip）。 */
export function getCapturePlatformTips(): string[] {
  return []
}

export async function chooseVideo(opts?: ChooseVideoOptions): Promise<ChosenVideo> {
  const sourceType: ('album' | 'camera')[] =
    opts?.source === 'camera'
      ? ['camera']
      : opts?.source === 'album'
        ? ['album']
        : ['album', 'camera']

  if (process.env.TARO_ENV === 'weapp') {
    // W8-T1：chooseMedia 属于隐私 API，调用前必须过微信隐私授权弹窗。
    await ensurePrivacyAuthorized('chooseMedia')
    const res = await Taro.chooseMedia({
      count: 1,
      mediaType: ['video'],
      sourceType,
      maxDuration: opts?.maxDurationSeconds || 30,
      camera: 'back',
    })
    const f = res.tempFiles[0] as typeof res.tempFiles[number] & {
      thumbTempFilePath?: string
    }
    return {
      filePath: f.tempFilePath,
      size: f.size,
      duration: f.duration || 0,
      width: f.width || 0,
      height: f.height || 0,
      thumbTempFilePath: f.thumbTempFilePath,
      preset: 'standard',
    }
  }

  throw new Error(`不支持的平台: ${process.env.TARO_ENV}`)
}

/** 调试 / SP-1：把选片结果打成一行摘要 */
export function summarizeChosenVideo(
  source: string,
  video: ChosenVideo,
): string {
  return formatVideoPickSummary({
    source,
    preset: video.preset,
    width: video.width,
    height: video.height,
    duration: video.duration,
    size: video.size,
    filePath: video.filePath,
  })
}
