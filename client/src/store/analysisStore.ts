/**
 * 分析任务的瞬时状态（不持久化）
 *
 * 用途：
 * - `currentAnalysisId`：params → waiting 跳转之间接力，首页 CTA 也能快速"回到当前任务"
 * - `recentCompleted`：最近一条完成的分析，供首页"最近分析"卡片免去再拉列表
 * - `pendingSwingSelection`：params → select-swing 之间暂存创建参数与候选列表
 *
 * 不持久化的原因：小程序冷启动 2 秒内会重新 bootstrap，走 listAnalyses 拉真实数据
 * 更可靠；"最近分析"也应以服务端为准。只有在同一会话内反复切页时有价值。
 */

import { create } from 'zustand'
import type {
  AnalysisListItem,
  AnalysisMode,
  AnalysisStatusResponse,
  SwingCandidateItem,
} from '@/types/analysis'
import type { CameraAngle, ClubType } from '@/types/api'

export interface PendingSwingSelection {
  uploadId: string
  cameraAngle: CameraAngle
  clubType: ClubType
  mode: AnalysisMode
  targetYardage?: number
  duration: number
  size: number
  swingCandidates: SwingCandidateItem[]
  defaultSelectedIndex: number
}

interface AnalysisState {
  currentAnalysisId: string | null
  currentStatus: AnalysisStatusResponse | null
  recentCompleted: AnalysisListItem | null
  pendingSwingSelection: PendingSwingSelection | null

  setCurrent(analysisId: string): void
  updateStatus(status: AnalysisStatusResponse): void
  clearCurrent(): void
  setRecentCompleted(item: AnalysisListItem | null): void
  setPendingSwingSelection(payload: PendingSwingSelection): void
  clearPendingSwingSelection(): void
}

export const useAnalysisStore = create<AnalysisState>((set) => ({
  currentAnalysisId: null,
  currentStatus: null,
  recentCompleted: null,
  pendingSwingSelection: null,

  setCurrent(analysisId: string) {
    set({ currentAnalysisId: analysisId, currentStatus: null })
  },
  updateStatus(status: AnalysisStatusResponse) {
    set({ currentStatus: status })
  },
  clearCurrent() {
    set({ currentAnalysisId: null, currentStatus: null })
  },
  setRecentCompleted(item: AnalysisListItem | null) {
    set({ recentCompleted: item })
  },
  setPendingSwingSelection(payload: PendingSwingSelection) {
    set({ pendingSwingSelection: payload })
  },
  clearPendingSwingSelection() {
    set({ pendingSwingSelection: null })
  },
}))
