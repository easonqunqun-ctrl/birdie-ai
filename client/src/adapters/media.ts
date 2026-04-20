/**
 * 跨端视频拍摄/选择 adapter
 *
 * 微信小程序：Taro.chooseMedia
 * React Native App：react-native-image-picker
 */

import Taro from '@tarojs/taro'

export interface ChosenVideo {
  filePath: string
  size: number
  duration: number
  width: number
  height: number
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
    const res = await Taro.chooseMedia({
      count: 1,
      mediaType: ['video'],
      sourceType,
      maxDuration: opts?.maxDurationSeconds || 30,
      camera: 'back'
    })
    const f = res.tempFiles[0]
    return {
      filePath: f.tempFilePath,
      size: f.size,
      duration: f.duration || 0,
      width: f.width || 0,
      height: f.height || 0
    }
  }

  if (process.env.TARO_ENV === 'rn') {
    // TODO: 接入 react-native-image-picker
    // import { launchCamera, launchImageLibrary } from 'react-native-image-picker'
    throw new Error('RN 端视频选择待 W3 接入 react-native-image-picker')
  }

  throw new Error(`不支持的平台: ${process.env.TARO_ENV}`)
}
