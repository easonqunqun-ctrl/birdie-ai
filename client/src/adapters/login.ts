/**
 * 跨端登录 adapter
 *
 * 微信小程序：用 wx.login() 拿到临时 code，发给后端换 openid
 * React Native App：用微信开放平台 SDK（react-native-wechat-lib）
 *
 * 通过 process.env.TARO_ENV 在编译期决定走哪个分支，最终产物不会包含另一端的代码
 */

import Taro from '@tarojs/taro'

declare const WECHAT_OPEN_APPID: string

export interface LoginResult {
  code: string
  /** 端类型，便于后端区分小程序 vs App */
  platform: 'weapp' | 'rn'
}

export async function nativeLogin(): Promise<LoginResult> {
  if (process.env.TARO_ENV === 'weapp') {
    return loginWeapp()
  }
  if (process.env.TARO_ENV === 'rn') {
    return loginRN()
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

async function loginRN(): Promise<LoginResult> {
  const appid = typeof WECHAT_OPEN_APPID !== 'undefined' ? WECHAT_OPEN_APPID.trim() : ''
  if (!appid) {
    throw new Error(
      '未配置 TARO_APP_WECHAT_OPEN_APPID：请在 .env 中填微信开放平台移动应用 AppID',
    )
  }

  type WeChatApi = {
    registerApp: (appId: string, universalLink?: string) => Promise<boolean>
    sendAuthRequest: (
      scope: string,
      state: string,
    ) => Promise<{ errCode?: number; code?: string; errStr?: string }>
  }

  let WeChat: WeChatApi
  try {
    const pkg = await import(
      /* webpackIgnore: true */
      'react-native-wechat-lib'
    )
    WeChat = ((pkg as { default?: WeChatApi }).default ?? pkg) as WeChatApi
  } catch {
    throw new Error('未安装原生依赖 react-native-wechat-lib（仅 RN 打包需要）')
  }

  await WeChat.registerApp(appid, '')
  const res = await WeChat.sendAuthRequest('snsapi_userinfo', 'lingyi_golf_login')
  if ((res as { errCode?: number }).errCode !== undefined && (res as { errCode?: number }).errCode !== 0) {
    throw new Error(
      `微信授权失败：${(res as { errStr?: string }).errStr || String((res as { errCode?: number }).errCode)}`,
    )
  }
  const code = (res as { code?: string }).code
  if (!code) {
    throw new Error('微信授权未返回 code')
  }
  return { code, platform: 'rn' }
}
