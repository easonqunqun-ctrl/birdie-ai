import { http } from './request'

/** POST /v1/feedback 响应（与 backend/app/schemas/feedback.py::FeedbackCreated 对齐） */
export interface FeedbackCreated {
  feedback_id: string
}

export interface FeedbackCreateRequest {
  content: string
  contact?: string
}

/**
 * 意见反馈（docs/02 §2.6）。
 *
 * 服务端校验：1–500 字 + 60s 节流（重复提交 429 → toast「反馈太频繁」）。
 */
export const feedbackService = {
  submit(payload: FeedbackCreateRequest) {
    return http.post<FeedbackCreated>('/feedback', {
      content: payload.content,
      contact: payload.contact,
    })
  },
}
