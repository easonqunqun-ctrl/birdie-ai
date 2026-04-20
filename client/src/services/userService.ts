import type {
  OnboardingRequest,
  User,
  UserUpdateRequest,
  WechatLoginRequest,
  WechatLoginResponse
} from '@/types/api'
import { http } from './request'

export const userService = {
  wechatLogin(payload: WechatLoginRequest) {
    return http.post<WechatLoginResponse>('/auth/wechat-login', payload, { noAuth: true })
  },
  refreshToken() {
    return http.post<{ token: string; expires_in: number }>('/auth/refresh-token', {})
  },
  getMe() {
    return http.get<User>('/users/me')
  },
  completeOnboarding(payload: OnboardingRequest) {
    return http.post<User>('/users/me/onboarding', payload)
  },
  updateMe(payload: UserUpdateRequest) {
    return http.patch<User>('/users/me', payload)
  }
}
