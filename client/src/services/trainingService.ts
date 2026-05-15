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
  /**
   * 把一份分析报告的 issues 同步加入当周训练计划。
   * 幂等：同 drill 不会重复添加任务。
   * 上游错误码：40015（已分析失败 / sample / 没有 issue），40016（drill 库缺失），
   * 40402（分析不存在），40302（不是当前用户）。
   *
   * silent=true：调用方负责文案与 modal，请求层不重复 toast。
   */
  addToPlanFromAnalysis(analysisId: string) {
    return http.post<TrainingPlanDetail>(
      `/training-plan/from-analysis/${analysisId}`,
      undefined,
      { silent: true },
    )
  },
  listPracticeLogs(month: string) {
    return http.get<PracticeLogItem[]>(`/users/me/practice-logs?month=${month}`)
  }
}
