import AnalysisCard from '../AnalysisCard'
import type { AnalysisCardAttachment } from '@/types/chat'

describe('AnalysisCard', () => {
  it('导出组件', () => {
    expect(AnalysisCard).toBeDefined()
  })

  it('AnalysisCardAttachment 类型字段', () => {
    const att: AnalysisCardAttachment = {
      type: 'analysis_card',
      analysis_id: 'ana_1',
      overall_score: 82,
    }
    expect(att.analysis_id).toBe('ana_1')
  })
})
