import Taro from '@tarojs/taro'

const TOKEN_KEY = 'auth_token'
const USER_KEY = 'auth_user'
const ROLE_KEY = 'auth_role'
const ANALYSIS_GUIDE_SEEN_KEY = 'analysis_guide_seen'
const AGREED_TERMS_KEY = 'agreed_terms'

/**
 * 用户协议 / 隐私政策当前版本号。
 * 协议文本有任何修订（新增/删除条款、法务重大调整）必须 bump，
 * 老用户会在下一次启动被 consent 页重新拦截同意。
 * 仅文案排版调整（错别字、标点）不需要 bump。
 */
export const CURRENT_TERMS_VERSION = 'v1.2'

export interface AgreedTermsRecord {
  /** 用户同意的协议版本号 */
  version: string
  /** 同意时间戳（ms） */
  agreedAt: number
}

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
  setRole(role: 'user' | 'coach'): void {
    Taro.setStorageSync(ROLE_KEY, role)
  },
  getRole(): 'user' | 'coach' {
    const role = Taro.getStorageSync(ROLE_KEY)
    return role === 'coach' ? 'coach' : 'user'
  },
  clearRole(): void {
    Taro.removeStorageSync(ROLE_KEY)
  },
  setUser<T>(user: T): void {
    Taro.setStorageSync(USER_KEY, user)
  },
  getUser<T = unknown>(): T | null {
    const u = Taro.getStorageSync(USER_KEY)
    return u || null
  },
  clearUser(): void {
    Taro.removeStorageSync(USER_KEY)
  },

  /** 拍摄引导页是否已看过（首次进 capture 页会展示完整指南） */
  hasSeenAnalysisGuide(): boolean {
    return !!Taro.getStorageSync(ANALYSIS_GUIDE_SEEN_KEY)
  },
  markAnalysisGuideSeen(): void {
    Taro.setStorageSync(ANALYSIS_GUIDE_SEEN_KEY, '1')
  },
  clearAnalysisGuideSeen(): void {
    Taro.removeStorageSync(ANALYSIS_GUIDE_SEEN_KEY)
  },

  /**
   * 读取用户同意的协议记录。
   * 返回 null 时表示从未同意；版本号不等于 CURRENT_TERMS_VERSION 时
   * 也应视为"未同意"并重新拦截（版本升级场景）。
   */
  getAgreedTerms(): AgreedTermsRecord | null {
    const raw = Taro.getStorageSync(AGREED_TERMS_KEY)
    if (!raw || typeof raw !== 'object') return null
    const rec = raw as AgreedTermsRecord
    if (typeof rec.version !== 'string' || typeof rec.agreedAt !== 'number') {
      return null
    }
    return rec
  },
  setAgreedTerms(version: string): void {
    const rec: AgreedTermsRecord = { version, agreedAt: Date.now() }
    Taro.setStorageSync(AGREED_TERMS_KEY, rec)
  },
  clearAgreedTerms(): void {
    Taro.removeStorageSync(AGREED_TERMS_KEY)
  },
  /** 是否已同意当前版本协议；拦截页用这个统一判断 */
  hasAgreedCurrentTerms(): boolean {
    const rec = this.getAgreedTerms()
    return !!rec && rec.version === CURRENT_TERMS_VERSION
  },

  /**
   * 危险操作：清空设备上**所有** storage（含协议同意、引导标记等设备级数据）。
   *
   * ⚠ 仅在以下场景使用：
   *   - 调试/开发清缓存
   *   - 严重的本地数据损坏需要强制重置
   *
   * 普通的「退出登录 / 注销账号」请使用 {@link clearAuthSession}，避免误删
   * `agreed_terms`（清掉后老用户每次重启都被合规弹窗拦截，是合规体验灾难）。
   */
  clearAll(): void {
    Taro.clearStorageSync()
  },

  /**
   * 退出登录 / 注销账号专用：只清账号身份相关 storage。
   * 设备级数据（协议同意版本、引导是否已看过）保留 —— 因为这些是
   * "本机/本人"维度的状态，与切换微信账号无关。
   */
  clearAuthSession(): void {
    Taro.removeStorageSync(TOKEN_KEY)
    Taro.removeStorageSync(USER_KEY)
    Taro.removeStorageSync(ROLE_KEY)
  }
}
