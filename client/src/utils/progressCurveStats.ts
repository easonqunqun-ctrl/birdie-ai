/**
 * 进步曲线统计与序列派生（Q-B3 / P-03）
 *
 * 纯函数；供 training/index 与 jest 共用。
 */

import { PHASE_LABEL, PHASE_ORDER, type SwingPhaseKey } from '@/constants/phaseLabels'

/** 与 backend AnalysisProgressPoint 对齐 */
export interface ProgressPoint {
  analysis_id: string
  analyzed_at: string
  overall_score: number
  phase_scores?: Record<string, number> | null
}

/** 折线图维度：综合分或六维之一 */
export type ProgressDimension = 'overall' | SwingPhaseKey

export interface ProgressStatCards {
  totalAnalyses: number
  totalPractices: number
  streakDays: number
  /** 窗口内综合分变化（末点 − 首点）；不足 2 点时为 null */
  windowScoreDelta: number | null
  /** 六维中首末对比提升最大的一项 */
  bestImprovement: { phase: SwingPhaseKey; label: string; delta: number } | null
}

export interface LineSeriesPoint {
  index: number
  value: number
  /** 短日期标签 M/D */
  label: string
}

const PHASE_KEYS = PHASE_ORDER as readonly SwingPhaseKey[]

/** ISO → 短日期 `M/D`（本地时区） */
export function shortChartDate(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso.slice(5, 10) || '—'
  return `${d.getMonth() + 1}/${d.getDate()}`
}

/** 从进步曲线点派生折线序列 */
export function seriesForDimension(
  points: ProgressPoint[],
  dimension: ProgressDimension,
): LineSeriesPoint[] {
  const out: LineSeriesPoint[] = []
  points.forEach((p, index) => {
    let value: number | null = null
    if (dimension === 'overall') {
      value = p.overall_score
    } else {
      value = p.phase_scores?.[dimension] ?? null
    }
    if (value === null || Number.isNaN(value)) return
    out.push({
      index,
      value: Math.max(0, Math.min(100, Math.round(value))),
      label: shortChartDate(p.analyzed_at),
    })
  })
  return out
}

/** 六维首末对比：找提升最大的一维（至少 2 个含该维数据的点） */
export function findBestPhaseImprovement(
  points: ProgressPoint[],
): { phase: SwingPhaseKey; label: string; delta: number } | null {
  let best: { phase: SwingPhaseKey; label: string; delta: number } | null = null
  for (const phase of PHASE_KEYS) {
    const vals: number[] = []
    for (const p of points) {
      const v = p.phase_scores?.[phase]
      if (typeof v === 'number' && !Number.isNaN(v)) vals.push(v)
    }
    if (vals.length < 2) continue
    const delta = vals[vals.length - 1] - vals[0]
    if (!best || delta > best.delta) {
      best = { phase, label: PHASE_LABEL[phase], delta }
    }
  }
  if (!best || best.delta <= 0) return null
  return best
}

export function computeProgressStatCards(
  points: ProgressPoint[],
  stats: {
    total_analyses?: number
    total_practices?: number
    streak_days?: number
  } | null | undefined,
): ProgressStatCards {
  const scores = points.map((p) => p.overall_score).filter((s) => typeof s === 'number')
  let windowScoreDelta: number | null = null
  if (scores.length >= 2) {
    windowScoreDelta = scores[scores.length - 1] - scores[0]
  }
  return {
    totalAnalyses: stats?.total_analyses ?? points.length,
    totalPractices: stats?.total_practices ?? 0,
    streakDays: stats?.streak_days ?? 0,
    windowScoreDelta,
    bestImprovement: findBestPhaseImprovement(points),
  }
}

export function formatDelta(delta: number | null | undefined): string {
  if (delta === null || delta === undefined || Number.isNaN(delta)) return '—'
  if (delta > 0) return `+${delta}`
  return String(delta)
}

/** ENG-05 余量：训练页进步曲线下方一句纵向叙事 */
export function formatProgressNarrative(
  stats: ProgressStatCards,
  points: ProgressPoint[],
): string | null {
  if (points.length < 2) return null
  if (stats.bestImprovement && stats.bestImprovement.delta > 0) {
    return `近 ${points.length} 次分析中，${stats.bestImprovement.label}提升 ${formatDelta(stats.bestImprovement.delta)} 分`
  }
  if (stats.windowScoreDelta !== null && stats.windowScoreDelta !== 0) {
    return `窗口内综合分 ${formatDelta(stats.windowScoreDelta)}（较最早一次同类型分析）`
  }
  return null
}
