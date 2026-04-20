/**
 * 跨端登录 adapter
 *
 * 微信小程序：用 wx.login() 拿到临时 code，发给后端换 openid
 * React Native App：用微信开放平台 SDK，需要 react-native-wechat-lib
 *
 * 通过 process.env.TARO_ENV 在编译期决定走哪个分支，最终产物不会包含另一端的代码
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
  if (process.env.TARO_ENV === 'rn') {
    return loginRN()
  }
  // h5 / dev 兜底：返回固定 mock code（后端会基于 hash 生成稳定 openid）
  return { code: `mock_dev_${Date.now()}`, platform: 'weapp' }
}

async function loginWeapp(): Promise<LoginResult> {
  const res = await Taro.login()
  if (!res.code) {
    throw new Error('微信登录失败：无法获取 code')
  }
  return { code: res.code, platform: 'weapp' }
}

async function loginRN(): Promise<LoginResult> {
  // TODO: 接入 react-native-wechat-lib
  // import * as WeChat from 'react-native-wechat-lib'
  // const isInstalled = await WeChat.isWXAppInstalled()
  // if (!isInstalled) throw new Error('未安装微信')
  // await WeChat.registerApp(WECHAT_OPEN_APPID, '小鸟 AI')
  // const result = await WeChat.sendAuthRequest('snsapi_userinfo', 'xiaoniao_login')
  // return { code: result.code, platform: 'rn' }

  // 占位：W2 实际接入 SDK 后替换
  return { code: `mock_rn_${Date.now()}`, platform: 'rn' }
}
