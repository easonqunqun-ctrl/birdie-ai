import Taro from '@tarojs/taro'

const TOKEN_KEY = 'auth_token'
const USER_KEY = 'auth_user'
const ANALYSIS_GUIDE_SEEN_KEY = 'analysis_guide_seen'

export const storage = {
  setToken(token: string): void {
    Taro.setStorageSync(TOKEN_KEY, token)
  },
  getToken(): string {
    return Taro.getStorageSync(TOKEN_KEY) || ''
  },
  clearToken(): void {
    Taro.removeStorageSync(TOKEN_KEY)
  },
  setUser<T>(user: T): void {
    Taro.setStorageSync(USER_KEY, user)
  },
  getUser<T = unknown>(): T | null {
    const u = Taro.getStorageSync(USER_KEY)
    return u || null
  },

  /** 拍摄引导页是否已看过（首次进 capture 页会展示完整指南） */
  hasSeenAnalysisGuide(): boolean {
    return !!Taro.getStorageSync(ANALYSIS_GUIDE_SEEN_KEY)
  },
  markAnalysisGuideSeen(): void {
    Taro.setStorageSync(ANALYSIS_GUIDE_SEEN_KEY, '1')
  },

  clearAll(): void {
    Taro.clearStorageSync()
  }
}
