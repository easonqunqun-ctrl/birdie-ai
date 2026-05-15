import { create } from 'zustand'
import { storage } from '@/utils/storage'
import { userService } from '@/services/userService'
import { nativeLogin } from '@/adapters/login'
import { isRequestError } from '@/services/request'
import type { User } from '@/types/api'

interface UserState {
  token: string
  user: User | null
  loading: boolean
  initialized: boolean

  /** 启动时调用：从本地缓存恢复 token，并拉取用户信息 */
  bootstrap: () => Promise<void>
  /** 微信一键登录。返回 is_new_user 与最新 user，供调用方按 onboarding 状态分流路由 */
  loginWithWechat: (inviteCode?: string) => Promise<{ isNewUser: boolean; user: User }>
  /** 拉取最新用户信息 */
  fetchMe: () => Promise<void>
  /** 退出登录 */
  logout: () => void
}

export const useUserStore = create<UserState>((set, get) => ({
  token: '',
  user: null,
  loading: false,
  initialized: false,

  async bootstrap() {
    const token = storage.getToken()
    if (!token) {
      set({ initialized: true })
      return
    }
    // 先尝试用本地缓存的 user 立即填充 UI，避免冷启动闪登录页
    const cachedUser = storage.getUser<User>() ?? null
    set({
      token,
      user: cachedUser,
      loading: true,
      // 有 cachedUser 时直接 initialized=true，让首页等不再卡 loading；
      // 若本次拉取失败，UI 也能继续以缓存数据展示
      initialized: Boolean(cachedUser),
    })
    try {
      const user = await userService.getMe()
      set({ user, loading: false, initialized: true })
    } catch (e: unknown) {
      // 关键：只在确认是「身份失效」时清 token；网络错误等保留登录态
      // - 401：request.ts 已 reLaunch 登录页 + 清 token，这里同步 store
      // - 5xx / network / bad_response：保留 token + cachedUser，UI 继续可用，下次有网时 fetchMe 再补
      if (isRequestError(e) && e.kind === 'http_unauthorized') {
        storage.clearToken()
        set({ token: '', user: null, loading: false, initialized: true })
      } else {
        // 弱网/后端短暂故障：不要踢用户，保留缓存
        if (process.env.NODE_ENV !== 'production') {
          // eslint-disable-next-line no-console
          console.warn('[userStore.bootstrap] non-fatal getMe failure, keep token:', e)
        }
        set({ loading: false, initialized: true })
      }
    }
  },

  async loginWithWechat(inviteCode?: string) {
    set({ loading: true })
    try {
      const { code } = await nativeLogin()
      const res = await userService.wechatLogin({ code, invite_code: inviteCode })
      storage.setToken(res.token)
      storage.setUser(res.user)
      set({ token: res.token, user: res.user, loading: false, initialized: true })
      return { isNewUser: res.is_new_user, user: res.user }
    } catch (e) {
      set({ loading: false })
      throw e
    }
  },

  async fetchMe() {
    if (!get().token) return
    const user = await userService.getMe()
    set({ user })
    storage.setUser(user)
  },

  logout() {
    // P1-C2：只清账号身份，不动协议同意（agreed_terms）/ 引导标记等
    // 设备级数据。原本 clearAll() 会让退出后再登录的老用户被合规弹窗
    // 反复拦截，体验灾难。
    storage.clearAuthSession()
    set({ token: '', user: null })
  }
}))
