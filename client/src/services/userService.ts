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
    const path =
      process.env.TARO_ENV === 'rn'
        ? '/auth/wechat-open-login'
        : '/auth/wechat-login'
    return http.post<WechatLoginResponse>(path, payload, { noAuth: true })
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
  },
  requestAccountDeletion(confirmText: string) {
    return http.post<User>('/users/me/account-deletion', {
      confirm_text: confirmText,
    })
  },
  cancelAccountDeletion() {
    return http.post<User>('/users/me/account-deletion/cancel', {})
  },
  getAnalysisProgress() {
    return http.get<{ points: { analysis_id: string; analyzed_at: string; overall_score: number }[] }>(
      '/users/me/analysis-progress',
    )
  }
}
