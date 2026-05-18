import { http } from './request'

/**
 * 分享报告相关类型 + 服务（W7-T5）。
 * 对齐 `backend/app/schemas/share.py`.
 */
export type ShareType = 'report' | 'invite_poster' | 'moments'

export interface ShareLogRequest {
  share_type: ShareType
  target_id?: string
}

export interface ShareLogResponse {
  id: string
  share_type: ShareType
  created_at: string
}

export interface PublicReportIssue {
  name: string
  severity: 'high' | 'medium' | 'low' | string
}

export interface PublicReport {
  id: string
  overall_score: number | null
  score_level: string | null
  camera_angle: string
  club_type: string
  thumbnail_url: string | null
  issues: PublicReportIssue[]
  issues_total: number
  /** 与完整报告 `quality_warnings` 一致；脱敏接口仍展示拍摄条件提示 */
  quality_warnings?: string[]
  analyzed_at: string | null
  owner_nickname_masked: string
}

export const shareService = {
  logShare(payload: ShareLogRequest) {
    // silent：埋点失败不弹 toast；用户已经分享成功，不能因为埋点请求抖动打扰
    return http.post<ShareLogResponse>('/shares/log', payload, { silent: true })
  },
  getPublicReport(analysisId: string) {
    return http.get<PublicReport>(`/analyses/${analysisId}/public`, {
      noAuth: true,
      silent: true
    })
  }
}
