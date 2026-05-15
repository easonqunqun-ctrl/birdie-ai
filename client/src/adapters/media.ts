/**
 * 跨端视频拍摄/选择 adapter
 *
 * 微信小程序：Taro.chooseMedia
 * React Native App：react-native-image-picker
 */

import Taro from '@tarojs/taro'
import { ensurePrivacyAuthorized } from '@/utils/privacy'

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
}

export async function chooseVideo(opts?: {
  source?: 'camera' | 'album' | 'both'
  maxDurationSeconds?: number
}): Promise<ChosenVideo> {
  const sourceType: ('album' | 'camera')[] =
    opts?.source === 'camera' ? ['camera']
      : opts?.source === 'album' ? ['album']
      : ['album', 'camera']

  if (process.env.TARO_ENV === 'weapp') {
    // W8-T1：chooseMedia 属于隐私 API，调用前必须过微信隐私授权弹窗。
    await ensurePrivacyAuthorized('chooseMedia')
    const res = await Taro.chooseMedia({
      count: 1,
      mediaType: ['video'],
      sourceType,
      maxDuration: opts?.maxDurationSeconds || 30,
      camera: 'back'
    })
    const f = res.tempFiles[0] as typeof res.tempFiles[number] & { thumbTempFilePath?: string }
    return {
      filePath: f.tempFilePath,
      size: f.size,
      duration: f.duration || 0,
      width: f.width || 0,
      height: f.height || 0,
      thumbTempFilePath: f.thumbTempFilePath,
    }
  }

  if (process.env.TARO_ENV === 'rn') {
    type RNPicker = typeof import('react-native-image-picker')
    let launchImageLibrary: RNPicker['launchImageLibrary']
    let launchCamera: RNPicker['launchCamera']

    try {
      const mod = (await import(
        /* webpackIgnore: true */
        'react-native-image-picker'
      )) as RNPicker
      launchImageLibrary = mod.launchImageLibrary
      launchCamera = mod.launchCamera
    } catch {
      throw new Error('未安装 react-native-image-picker（仅 RN 打包需要）')
    }

    const durationLimit = opts?.maxDurationSeconds ?? 30

    const baseLib = {
      mediaType: 'video' as const,
      selectionLimit: 1,
      videoQuality: 'high' as const,
      durationLimit,
      ...(opts?.source === 'album'
        ? {}
        : { presentationStyle: 'pageSheet' as const }),
    }

    const pick =
      opts?.source === 'camera'
        ? await launchCamera({
            mediaType: 'video',
            videoQuality: 'high',
            durationLimit,
            cameraType: 'back',
            saveToPhotos: false,
          })
        : await launchImageLibrary(baseLib)

    if (pick.didCancel || !pick.assets?.[0]?.uri) {
      throw new Error('已取消选择视频')
    }
    const a = pick.assets[0]
    const uri = a.uri!
    const durationRaw = typeof a.duration === 'number' ? a.duration : 0
    /** iOS 常见为毫秒，Android 常为秒 —— >1000 时按毫秒转秒 */
    const durationSeconds =
      durationRaw > 1000 ? durationRaw / 1000 : durationRaw
    return {
      filePath: uri,
      size: a.fileSize || 0,
      duration: durationSeconds,
      width: a.width || 0,
      height: a.height || 0,
      // 首帧预检可走后续缩略工具；暂无则后端 media-check fail-open。
      thumbTempFilePath: undefined,
    }
  }

  throw new Error(`不支持的平台: ${process.env.TARO_ENV}`)
}
