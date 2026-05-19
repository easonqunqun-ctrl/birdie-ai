/**
 * analysisStore.ts 单测：瞬时分析状态接力
 *
 * 关键不变式：
 *  - setCurrent 会清掉旧 status（避免新任务读到旧任务的进度）
 *  - clearCurrent 同时清 id 与 status
 *  - recentCompleted 可独立 set/null，不与 current 联动
 */

import { useAnalysisStore } from '@/store/analysisStore'
import type {
  AnalysisListItem,
  AnalysisStatusResponse,
} from '@/types/analysis'

function reset() {
  useAnalysisStore.setState({
    currentAnalysisId: null,
    currentStatus: null,
    recentCompleted: null,
  })
}

beforeEach(reset)

describe('useAnalysisStore.setCurrent', () => {
  test('设置 currentAnalysisId 并清空 status', () => {
    useAnalysisStore.setState({
      currentStatus: { status: 'processing' } as unknown as AnalysisStatusResponse,
    })
    useAnalysisStore.getState().setCurrent('a-new')
    expect(useAnalysisStore.getState().currentAnalysisId).toBe('a-new')
    expect(useAnalysisStore.getState().currentStatus).toBeNull()
  })
})

describe('useAnalysisStore.updateStatus', () => {
  test('只更新 currentStatus，不动 currentAnalysisId', () => {
    useAnalysisStore.getState().setCurrent('a1')
    const status = { status: 'completed', progress: 100 } as unknown as AnalysisStatusResponse
    useAnalysisStore.getState().updateStatus(status)
    expect(useAnalysisStore.getState().currentAnalysisId).toBe('a1')
    expect(useAnalysisStore.getState().currentStatus).toBe(status)
  })
})

describe('useAnalysisStore.clearCurrent', () => {
  test('清空 id 与 status', () => {
    useAnalysisStore.getState().setCurrent('a1')
    useAnalysisStore.getState().updateStatus({ status: 'processing' } as any)
    useAnalysisStore.getState().clearCurrent()
    expect(useAnalysisStore.getState().currentAnalysisId).toBeNull()
    expect(useAnalysisStore.getState().currentStatus).toBeNull()
  })

  test('不触碰 recentCompleted', () => {
    const item = { id: 'a-prev', status: 'completed' } as unknown as AnalysisListItem
    useAnalysisStore.getState().setRecentCompleted(item)
    useAnalysisStore.getState().setCurrent('a1')
    useAnalysisStore.getState().clearCurrent()
    expect(useAnalysisStore.getState().recentCompleted).toBe(item)
  })
})

describe('useAnalysisStore.setRecentCompleted', () => {
  test('可以传 null 来清除', () => {
    const item = { id: 'a-prev' } as unknown as AnalysisListItem
    useAnalysisStore.getState().setRecentCompleted(item)
    expect(useAnalysisStore.getState().recentCompleted).toBe(item)
    useAnalysisStore.getState().setRecentCompleted(null)
    expect(useAnalysisStore.getState().recentCompleted).toBeNull()
  })
})
