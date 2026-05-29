/**
 * P2-M12-05 · 用户报告 vs 职业镜头雷达 / 六维表数据构建。
 *
 * 职业镜头当前仅有 overall_score + features_snapshot；无分阶段评分明细时，
 * 以综合分作为六维参考基线（虚线多边形），并在表头注明。
 */

import { PHASE_LABEL, PHASE_ORDER, type SwingPhaseKey } from '@/constants/phaseLabels'
import type { RadarAxis } from '@/components/radar-chart-types'
import type { AnalysisReportResponse } from '@/types/analysis'
import type { ProSwingClipRead } from '@/services/prosService'

export interface ProPhaseCompareRow {
  key: SwingPhaseKey
  label: string
  userScore: number | null
  proScore: number | null
  delta: number | null
  proIsReference: boolean
}

export function buildUserRadarAxes(report: AnalysisReportResponse): RadarAxis[] {
  if (!report.phase_scores) return []
  return PHASE_ORDER.map((key) => {
    const ps = report.phase_scores?.[key]
    return {
      key,
      label: PHASE_LABEL[key],
      score: ps?.score ?? 0,
      is_weakest: ps?.is_weakest ?? false,
    }
  })
}

/** 从职业镜头推导六维参考分：优先 features_snapshot 里与 phase key 同名的数值。 */
export function deriveProPhaseScores(
  clip: ProSwingClipRead,
): Record<SwingPhaseKey, number | null> {
  const snap = clip.features_snapshot ?? {}
  const fallback =
    typeof clip.overall_score === 'number' ? clip.overall_score : null
  const out = {} as Record<SwingPhaseKey, number | null>
  for (const key of PHASE_ORDER) {
    const raw = snap[key]
    if (typeof raw === 'number' && Number.isFinite(raw)) {
      out[key] = clampScore(raw)
    } else {
      out[key] = fallback
    }
  }
  return out
}

export function proScoresAreReferenceOnly(clip: ProSwingClipRead): boolean {
  const snap = clip.features_snapshot ?? {}
  return !PHASE_ORDER.some((key) => typeof snap[key] === 'number')
}

export function buildProRadarAxes(
  clip: ProSwingClipRead,
  userAxes: RadarAxis[],
): RadarAxis[] {
  const phaseScores = deriveProPhaseScores(clip)
  return userAxes.map((axis) => ({
    key: axis.key,
    label: axis.label,
    score: phaseScores[axis.key as SwingPhaseKey] ?? 0,
    is_weakest: false,
  }))
}

export function buildProPhaseCompareRows(
  report: AnalysisReportResponse,
  clip: ProSwingClipRead,
): ProPhaseCompareRow[] {
  const proScores = deriveProPhaseScores(clip)
  const referenceOnly = proScoresAreReferenceOnly(clip)
  return PHASE_ORDER.map((key) => {
    const userRaw = report.phase_scores?.[key]?.score
    const userScore = typeof userRaw === 'number' ? userRaw : null
    const proScore = proScores[key]
    const delta =
      userScore != null && proScore != null ? userScore - proScore : null
    return {
      key,
      label: PHASE_LABEL[key],
      userScore,
      proScore,
      delta,
      proIsReference: referenceOnly,
    }
  })
}

function clampScore(value: number): number {
  if (value <= 10) return Math.max(0, Math.min(100, value * 10))
  if (value > 100) return Math.max(0, Math.min(100, value / 10))
  return Math.max(0, Math.min(100, value))
}
