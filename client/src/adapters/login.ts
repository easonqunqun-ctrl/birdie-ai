/**
 * 跨端登录 adapter
 *
 * 微信小程序：用 wx.login() 拿到临时 code，发给后端换 openid
 *
 * 通过 process.env.TARO_ENV 在编译期决定走哪个分支，最终产物不会包含另一端的代码。
 * （原 React Native 分支已移除，App 端改用独立 Flutter 工程。）
 */

import Taro from '@tarojs/taro'

export interface LoginResult {
  code: string
  /** 端类型，便于后端区分小程序 vs App */
  platform: 'weapp' | 'rn'
}

export async function nativeLogin(): Promise<LoginResult> {
  if (process.env.TARO_ENV === 'weapp') {
    return loginWeapp()
  }
  // h5 / dev 兜底：返回固定 mock code（后端会基于 hash 生成稳定 openid）
  return { code: `mock_dev_${Date.now()}`, platform: 'weapp' }
}

async function loginWeapp(): Promise<LoginResult> {
  // wx.login 为隐私接口：须由用户点击带 open-type=agreePrivacyAuthorization 的 Button
  // 完成微信侧同步后再调用（见 pages/login）。此处不再 requirePrivacyAuthorize，
  // 避免与官方按钮链路重复弹窗或真机静默失败。
  const res = await Taro.login()
  const errMsg = (res as { errMsg?: string }).errMsg || ''
  if (!res.code) {
    if (errMsg) {
      throw new Error(`微信登录失败：${errMsg}`)
    }
    throw new Error('微信登录失败：无法获取 code（请检查后台是否已声明 wx.login 等隐私类型）')
  }
  if (errMsg && !/[:：]ok\b/i.test(errMsg)) {
    throw new Error(`微信登录失败：${errMsg}`)
  }
  return { code: res.code, platform: 'weapp' }
}
