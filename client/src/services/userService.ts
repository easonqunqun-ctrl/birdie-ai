import type {
  OnboardingRequest,
  User,
  UserUpdateRequest,
  WechatLoginRequest,
  WechatLoginResponse
} from '@/types/api'
import { http } from './request'

/** 真机弱网：默认 wx.request 15s 易超时，身份相关接口单独放宽 */
const AUTH_READ_TIMEOUT_MS = 60000

export const userService = {
  wechatLogin(payload: WechatLoginRequest) {
    const path =
      process.env.TARO_ENV === 'rn'
        ? '/auth/wechat-open-login'
        : '/auth/wechat-login'
    return http.post<WechatLoginResponse>(path, payload, {
      noAuth: true,
      timeout: AUTH_READ_TIMEOUT_MS,
    })
  },
  refreshToken() {
    return http.post<{ token: string; expires_in: number }>(
      '/auth/refresh-token',
      {},
      { timeout: AUTH_READ_TIMEOUT_MS },
    )
  },
  getMe() {
    return http.get<User>('/users/me', { timeout: AUTH_READ_TIMEOUT_MS })
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
  getAnalysisProgress(windowDays?: number) {
    const qs =
      typeof windowDays === 'number' && windowDays > 0
        ? `?window_days=${windowDays}`
        : ''
    return http.get<{
      points: {
        analysis_id: string
        analyzed_at: string
        overall_score: number
        phase_scores?: Record<string, number> | null
      }[]
    }>(`/users/me/analysis-progress${qs}`)
  },
  /**
   * P2-W16-A · ENG-05 · 同水平+同器材的得分分位（你击败 X% 同水平用户）.
   *
   * 服务端策略：
   * - cohort 同 ``user.golf_level`` + 同 ``club_type`` 的其他用户最近一次综合分
   * - cohort_size < 5 → ``percentile = null``，前端**必须**隐藏分位 UI
   *   （别拿 1-2 个对比就出"击败 50%"骗自己）
   * - 用户没填 ``golf_level`` 时 cohort 不限定 level（"全部水平"）
   */
  getScorePercentile(clubType: string) {
    return http.get<{
      user_score: number | null
      percentile: number | null
      cohort_size: number
      cohort_label: string
      median: number | null
      club_type: string
      golf_level: string | null
      computed_at: string
    }>(`/users/me/score-percentile?club_type=${encodeURIComponent(clubType)}`)
  },
}
