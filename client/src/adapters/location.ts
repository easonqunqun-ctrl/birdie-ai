/**
 * 跨端定位 adapter（M9-05 常去球馆 · 附近球馆）
 *
 * 微信小程序须同时满足：
 * - app.config `requiredPrivateInfos: ['getLocation']` + `permission.scope.userLocation`
 * - 公众平台《用户隐私保护指引》勾选「位置信息 / getLocation」
 * - 运行时 `ensurePrivacyAuthorized('getLocation')` + `scope.userLocation` 授权
 */

import Taro from '@tarojs/taro'
import { ensurePrivacyAuthorized, PrivacyDeniedError } from '@/utils/privacy'

export type LocationErrorCode = 'denied' | 'unavailable'

export class LocationError extends Error {
  readonly code: LocationErrorCode

  constructor(code: LocationErrorCode, message: string) {
    super(message)
    this.name = 'LocationError'
    this.code = code
  }
}

const DENIED_MSG = '定位权限未开启，请在设置中允许使用位置信息'
const PRIVACY_MSG = '需同意隐私协议后才能使用定位功能'

function isAuthDenied(errMsg: string | undefined): boolean {
  if (!errMsg) return false
  return /auth deny|authorize|permission denied|no permission|权限|requiredPrivateInfos/i.test(
    errMsg,
  )
}

async function ensureUserLocationScope(): Promise<void> {
  const setting = await Taro.getSetting()
  const granted = setting.authSetting?.['scope.userLocation']
  if (granted === true) return
  if (granted === false) {
    throw new LocationError('denied', DENIED_MSG)
  }
  try {
    await Taro.authorize({ scope: 'scope.userLocation' })
  } catch {
    throw new LocationError('denied', DENIED_MSG)
  }
}

async function callGetLocation(): Promise<{ latitude: number; longitude: number }> {
  try {
    return await Taro.getLocation({ type: 'gcj02' })
  } catch (first) {
    const firstMsg = (first as { errMsg?: string })?.errMsg
    if (isAuthDenied(firstMsg)) {
      throw first
    }
    // 部分机型 isHighAccuracy 会额外失败；普通精度再试一次
    return Taro.getLocation({ type: 'gcj02', isHighAccuracy: true })
  }
}

/** 获取 GCJ-02 坐标；用户拒绝或未声明隐私接口时抛 LocationError。 */
export async function getCurrentGcj02Location(): Promise<{
  latitude: number
  longitude: number
}> {
  if (process.env.TARO_ENV !== 'weapp') {
    throw new LocationError('unavailable', '当前环境不支持定位')
  }

  try {
    await ensurePrivacyAuthorized('getLocation')
  } catch (e) {
    if (e instanceof PrivacyDeniedError) {
      throw new LocationError('denied', PRIVACY_MSG)
    }
    throw e
  }

  await ensureUserLocationScope()

  try {
    const loc = await callGetLocation()
    return { latitude: loc.latitude, longitude: loc.longitude }
  } catch (e) {
    if (e instanceof LocationError) {
      throw e
    }
    const errMsg = (e as { errMsg?: string })?.errMsg
    if (isAuthDenied(errMsg)) {
      throw new LocationError('denied', DENIED_MSG)
    }
    if (errMsg && /requiredPrivateInfos/i.test(errMsg)) {
      throw new LocationError(
        'unavailable',
        '小程序未声明定位接口，请更新到最新体验版',
      )
    }
    throw new LocationError('unavailable', '定位失败，请稍后重试')
  }
}

/** 引导用户到小程序设置页开启位置权限；返回是否点击了「去设置」。 */
export async function promptOpenLocationSettings(): Promise<boolean> {
  const res = await Taro.showModal({
    title: '需要位置权限',
    content: '用于查找附近球馆，请在设置中开启「位置信息」',
    confirmText: '去设置',
    cancelText: '取消',
  })
  if (!res.confirm) return false
  await Taro.openSetting()
  return true
}
