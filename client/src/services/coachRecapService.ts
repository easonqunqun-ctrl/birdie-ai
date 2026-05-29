/**
 * M8-07 · 教练教学报告 service。
 */

import { http } from './request'

export interface CoachRecapCreatePayload {
  session_date: string
  student_ids: string[]
  analysis_ids: string[]
  coach_manual_notes?: string
}

export interface CoachRecapCreateResponse {
  recap_id: string
  ai_summary: string
  status: string
  ai_summary_model?: string | null
}

export interface CoachRecapExportPdfResponse {
  pdf_url: string
  pdf_url_expires_at: string
}

export interface CoachRecapListItem {
  id: string
  session_date: string
  student_ids: string[]
  analysis_ids: string[]
  status: string
  ai_summary?: string | null
  pdf_url?: string | null
  pdf_url_expires_at?: string | null
  created_at: string
}

export interface CoachRecapListResponse {
  items: CoachRecapListItem[]
  total: number
}

export const coachRecapService = {
  create(payload: CoachRecapCreatePayload): Promise<CoachRecapCreateResponse> {
    return http.post<CoachRecapCreateResponse>('/coach/sessions/recap', payload)
  },

  exportPdf(recapId: string): Promise<CoachRecapExportPdfResponse> {
    return http.post<CoachRecapExportPdfResponse>(
      `/coach/sessions/${encodeURIComponent(recapId)}/export-pdf`,
      {},
    )
  },

  list(page = 1, pageSize = 20): Promise<CoachRecapListResponse> {
    const qs = `?page=${page}&page_size=${pageSize}`
    return http.get<CoachRecapListResponse>(`/coach/sessions/recaps${qs}`)
  },
}
