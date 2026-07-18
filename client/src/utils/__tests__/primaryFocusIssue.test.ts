import { pickPrimaryFocusIssue } from '@/utils/primaryFocusIssue'
import type { AnalysisIssueDetail } from '@/types/analysis'

function issue(
  partial: Partial<AnalysisIssueDetail> & Pick<AnalysisIssueDetail, 'type' | 'name' | 'severity'>,
): AnalysisIssueDetail {
  return {
    description: '',
    ...partial,
  } as AnalysisIssueDetail
}

describe('pickPrimaryFocusIssue', () => {
  it('returns null for empty', () => {
    expect(pickPrimaryFocusIssue([])).toBeNull()
    expect(pickPrimaryFocusIssue(null)).toBeNull()
  })

  it('picks highest severity', () => {
    const list = [
      issue({ type: 'a', name: '低', severity: 'low' }),
      issue({ type: 'b', name: '高', severity: 'high' }),
      issue({ type: 'c', name: '中', severity: 'medium' }),
    ]
    expect(pickPrimaryFocusIssue(list)?.type).toBe('b')
  })

  it('keeps first when severity ties', () => {
    const list = [
      issue({ type: 'a', name: '甲', severity: 'high' }),
      issue({ type: 'b', name: '乙', severity: 'high' }),
    ]
    expect(pickPrimaryFocusIssue(list)?.type).toBe('a')
  })
})
