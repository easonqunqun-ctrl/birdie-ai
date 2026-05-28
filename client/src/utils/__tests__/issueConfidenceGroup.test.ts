/**
 * P2-W10 · 报告页 issue confidence_tier 分组逻辑单测。
 *
 * 覆盖：
 * - 主路径：confirmed / leaning / hidden 各自归位
 * - V1 兜底：无 confidence_tier → 走 confident 区
 * - 排序：每组内 high > medium > low
 * - 输入异常：null / undefined / 空数组 / 未知 severity
 */

import { groupIssuesByConfidence } from '@/utils/issueConfidenceGroup'
import type { AnalysisIssueDetail } from '@/types/analysis'

function makeIssue(
  partial: Partial<AnalysisIssueDetail> & { type: string },
): AnalysisIssueDetail {
  return {
    type: partial.type,
    name: partial.name ?? partial.type,
    severity: partial.severity ?? 'medium',
    description: partial.description ?? '',
    key_frame_url: partial.key_frame_url ?? null,
    key_frame_timestamp: partial.key_frame_timestamp ?? null,
    confidence: partial.confidence,
    confidence_tier: partial.confidence_tier,
  }
}

describe('groupIssuesByConfidence', () => {
  test('null / undefined / 空数组 → 两组都空', () => {
    expect(groupIssuesByConfidence(null)).toEqual({ confident: [], hidden: [] })
    expect(groupIssuesByConfidence(undefined)).toEqual({ confident: [], hidden: [] })
    expect(groupIssuesByConfidence([])).toEqual({ confident: [], hidden: [] })
  })

  test('confirmed + leaning 进 confident，hidden 进 hidden', () => {
    const issues = [
      makeIssue({ type: 'a', confidence_tier: 'confirmed' }),
      makeIssue({ type: 'b', confidence_tier: 'leaning' }),
      makeIssue({ type: 'c', confidence_tier: 'hidden' }),
    ]
    const { confident, hidden } = groupIssuesByConfidence(issues)
    expect(confident.map((x) => x.type).sort()).toEqual(['a', 'b'])
    expect(hidden.map((x) => x.type)).toEqual(['c'])
  })

  test('V1 报告兜底：confidence_tier 缺失 → 进 confident（保持现状不打扰用户）', () => {
    const issues = [
      makeIssue({ type: 'old1' }),
      makeIssue({ type: 'old2', confidence: 0.4 }), // 即使 conf 低，无 tier 也按 confident
    ]
    const { confident, hidden } = groupIssuesByConfidence(issues)
    expect(confident).toHaveLength(2)
    expect(hidden).toHaveLength(0)
  })

  test('每组内 severity 排序：high > medium > low', () => {
    const issues = [
      makeIssue({ type: 'low_conf', severity: 'low', confidence_tier: 'confirmed' }),
      makeIssue({ type: 'high_conf', severity: 'high', confidence_tier: 'confirmed' }),
      makeIssue({ type: 'med_conf', severity: 'medium', confidence_tier: 'confirmed' }),
      makeIssue({ type: 'low_hid', severity: 'low', confidence_tier: 'hidden' }),
      makeIssue({ type: 'high_hid', severity: 'high', confidence_tier: 'hidden' }),
    ]
    const { confident, hidden } = groupIssuesByConfidence(issues)
    expect(confident.map((x) => x.type)).toEqual(['high_conf', 'med_conf', 'low_conf'])
    expect(hidden.map((x) => x.type)).toEqual(['high_hid', 'low_hid'])
  })

  test('未知 severity 排到末尾，不破坏分组', () => {
    const issues = [
      makeIssue({ type: 'unknown_sev', severity: 'critical' as any, confidence_tier: 'confirmed' }),
      makeIssue({ type: 'high_known', severity: 'high', confidence_tier: 'confirmed' }),
    ]
    const { confident } = groupIssuesByConfidence(issues)
    expect(confident.map((x) => x.type)).toEqual(['high_known', 'unknown_sev'])
  })

  test('全部 hidden → confident 空，hidden 完整保留', () => {
    const issues = [
      makeIssue({ type: 'a', confidence_tier: 'hidden', severity: 'high' }),
      makeIssue({ type: 'b', confidence_tier: 'hidden', severity: 'medium' }),
    ]
    const { confident, hidden } = groupIssuesByConfidence(issues)
    expect(confident).toEqual([])
    expect(hidden.map((x) => x.type)).toEqual(['a', 'b'])
  })

  test('不修改入参（不可变性）', () => {
    const issues = [
      makeIssue({ type: 'a', severity: 'low', confidence_tier: 'confirmed' }),
      makeIssue({ type: 'b', severity: 'high', confidence_tier: 'confirmed' }),
    ]
    const originalOrder = issues.map((x) => x.type)
    groupIssuesByConfidence(issues)
    expect(issues.map((x) => x.type)).toEqual(originalOrder)
  })

  test('真实 W9 场景：mixed tier + V1 兜底混存', () => {
    const issues = [
      // V2 confirmed 高严重度
      makeIssue({
        type: 'casting',
        severity: 'high',
        confidence: 0.91,
        confidence_tier: 'confirmed',
      }),
      // V2 leaning（confidence 0.65 落入 leaning 档）
      makeIssue({
        type: 'over_the_top',
        severity: 'medium',
        confidence: 0.65,
        confidence_tier: 'leaning',
      }),
      // V2 hidden（confidence 0.45 落入 hidden 档）
      makeIssue({
        type: 'early_extension',
        severity: 'medium',
        confidence: 0.45,
        confidence_tier: 'hidden',
      }),
      // V1 兜底（旧报告无 tier）
      makeIssue({ type: 'legacy_v1', severity: 'low' }),
    ]
    const { confident, hidden } = groupIssuesByConfidence(issues)
    expect(confident.map((x) => x.type)).toEqual(['casting', 'over_the_top', 'legacy_v1'])
    expect(hidden.map((x) => x.type)).toEqual(['early_extension'])
  })
})
