/**
 * PP-07：从「自信区」问题列表挑出本周主攻 1 项（严重度优先）。
 */

import type { AnalysisIssueDetail } from '@/types/analysis'
import { ISSUE_SEVERITY_ORDER } from '@/utils/issueConfidenceGroup'

function severityRank(s: string | null | undefined): number {
  return ISSUE_SEVERITY_ORDER[s ?? ''] ?? 9
}

/** 返回严重度最高的一条；列表空则 null */
export function pickPrimaryFocusIssue(
  confidentIssues: readonly AnalysisIssueDetail[] | null | undefined,
): AnalysisIssueDetail | null {
  if (!confidentIssues || confidentIssues.length === 0) return null
  let best = confidentIssues[0]
  for (let i = 1; i < confidentIssues.length; i += 1) {
    const cur = confidentIssues[i]
    if (severityRank(cur.severity) < severityRank(best.severity)) {
      best = cur
    }
  }
  return best
}
