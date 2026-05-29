/**
 * M12-09 · 教练报告批注（video_ref 引用职业镜头）。
 */

import type { ProPlayerRead, ProSwingClipRead } from '@/services/prosService'
import { http } from './request'

export type CoachAnnotationType = 'voice' | 'text' | 'sketch' | 'video_ref'

export interface CoachAnnotationClipRef {
  id: string
  analysis_id: string
  annotation_type: CoachAnnotationType
  pro_clip_id: string | null
  text_content: string | null
  is_visible: boolean
  created_at: string
  clip: ProSwingClipRead | null
  player: ProPlayerRead | null
  clip_unavailable: boolean
}

export interface CoachVideoRefCreate {
  pro_clip_id: string
  text_content?: string
}

export const coachAnnotationService = {
  listForAnalysis(analysisId: string) {
    return http.get<CoachAnnotationClipRef[]>(
      `/analyses/${analysisId}/coach-annotations`,
    )
  },
  listCoach(analysisId: string) {
    return http.get<CoachAnnotationClipRef[]>(
      `/coach/analyses/${analysisId}/annotations`,
    )
  },
  createVideoRef(analysisId: string, body: CoachVideoRefCreate) {
    return http.post<CoachAnnotationClipRef>(
      `/coach/analyses/${analysisId}/annotations`,
      {
        annotation_type: 'video_ref',
        pro_clip_id: body.pro_clip_id,
        text_content: body.text_content ?? null,
      },
    )
  },
  remove(annotationId: string) {
    return http.del<{ }>(`/coach/annotations/${annotationId}`)
  },
}
