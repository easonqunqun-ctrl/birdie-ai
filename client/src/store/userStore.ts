import { create } from 'zustand'
import { storage } from '@/utils/storage'
import { userService } from '@/services/userService'
import { nativeLogin } from '@/adapters/login'
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
    set({ token, loading: true })
    try {
      const user = await userService.getMe()
      set({ user, loading: false, initialized: true })
    } catch {
      // token 失效，清掉
      storage.clearToken()
      set({ token: '', user: null, loading: false, initialized: true })
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
    storage.clearToken()
    storage.clearAll()
    set({ token: '', user: null })
  }
}))
