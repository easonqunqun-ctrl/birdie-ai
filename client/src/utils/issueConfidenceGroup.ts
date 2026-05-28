/**
 * P2-W10：报告页问题诊断按 confidence_tier 分组。
 *
 * 设计目标
 * --------
 * W7+W9 ai_engine 给每个 issue 算了 confidence + tier（confirmed/leaning/hidden）。
 * W10 客户端兑现：
 * - confirmed / leaning / 无 tier（V1 兜底）→ 主区正常展示（合称 confident）
 * - hidden（confidence < 0.6）→ 折叠到「AI 不太确定」可展开区，
 *   避免低质量诊断对用户造成"AI 武断"印象
 *
 * 抽成 util 是为了：
 * 1. 把分组逻辑从 report.tsx 大组件解耦，方便 jest 测；
 * 2. 单一真源，未来 history.tsx / poster.tsx 复用时不会出现两份分组规则。
 */

import type { AnalysisIssueDetail, IssueConfidenceTier } from '@/types/analysis'

/**
 * 哪些 tier 算"AI 不够确定"——目前仅 hidden。
 * leaning 视觉上靠语气"可能存在·"软化，但仍展示在主区。
 */
const HIDDEN_TIERS: ReadonlySet<IssueConfidenceTier> = new Set(['hidden'])

export interface IssueGroupResult {
  /**
   * 主区展示：confirmed / leaning / 无 tier（V1 兜底）按 severity 排序后的列表
   */
  confident: AnalysisIssueDetail[]
  /**
   * 折叠区展示：tier=hidden 的诊断
   */
  hidden: AnalysisIssueDetail[]
}

/**
 * 严重度排序（与 report.tsx SEVERITY_SORT 一致）。
 * 抽常量后两处共用，避免漂移。
 */
export const ISSUE_SEVERITY_ORDER: Readonly<Record<string, number>> = {
  high: 0,
  medium: 1,
  low: 2,
}

function severityRank(s: string | null | undefined): number {
  return ISSUE_SEVERITY_ORDER[s ?? ''] ?? 9
}

/**
 * 按 confidence_tier 分组（保持每组内严重度排序）。
 *
 * - 没传 confidence_tier 字段（V1 引擎报告或老报告）视为 confident（保持现状）
 * - severity 未识别值排到最后
 */
export function groupIssuesByConfidence(
  issues: readonly AnalysisIssueDetail[] | null | undefined,
): IssueGroupResult {
  if (!issues || issues.length === 0) {
    return { confident: [], hidden: [] }
  }
  const confident: AnalysisIssueDetail[] = []
  const hidden: AnalysisIssueDetail[] = []
  for (const iss of issues) {
    if (iss.confidence_tier && HIDDEN_TIERS.has(iss.confidence_tier)) {
      hidden.push(iss)
    } else {
      confident.push(iss)
    }
  }
  const sortBySeverity = (a: AnalysisIssueDetail, b: AnalysisIssueDetail) =>
    severityRank(a.severity) - severityRank(b.severity)
  confident.sort(sortBySeverity)
  hidden.sort(sortBySeverity)
  return { confident, hidden }
}
