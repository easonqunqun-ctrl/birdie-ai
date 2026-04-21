import type {
  CompleteTaskRequest,
  CompleteTaskResponse,
  PracticeLogItem,
  TrainingPlanDetail
} from '@/types/training'
import { http } from './request'

/**
 * 训练计划 / 打卡 API（W7-T3）.
 *
 * 交互流程：
 *   页面挂载 → `getCurrentPlan()` → 若 null 展示"先上传一次挥杆视频"的空态
 *   点任务「完成」 → `completeTask(taskId)` → 用返回的 `current_streak_days`
 *     刷新首页 store
 */
export const trainingService = {
  getCurrentPlan() {
    return http.get<TrainingPlanDetail | null>('/users/me/training-plan/current')
  },
  completeTask(taskId: string, payload: CompleteTaskRequest = {}) {
    return http.post<CompleteTaskResponse>(
      `/training-plan/tasks/${taskId}/complete`,
      payload
    )
  },
  listPracticeLogs(month: string) {
    return http.get<PracticeLogItem[]>(`/users/me/practice-logs?month=${month}`)
  }
}
