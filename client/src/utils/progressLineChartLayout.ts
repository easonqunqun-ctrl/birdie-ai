/**
 * 进步曲线折线图布局（Canvas 2D 纯函数）
 *
 * Y 轴固定 0–100；X 轴按点数等分。
 */

// P2-W12-1：让进步曲线点能按 trust tier 着色（与 history mini 标签 / TrustBadge 色板一致）
export type LineChartTier = 'high' | 'medium' | 'low'

export interface LineChartInputPoint {
  value: number
  label: string
  /** V2 报告才传 tier；V1 / 默认 undefined → 走 accentColor */
  tier?: LineChartTier
}

export interface LineChartCoord {
  x: number
  y: number
  value: number
  label: string
  tier?: LineChartTier
}

export interface LineChartLayout {
  width: number
  height: number
  coords: LineChartCoord[]
  gridY: number[]
}

export const LINE_CHART_PADDING = {
  top: 16,
  right: 12,
  bottom: 32,
  left: 36,
} as const

/** 将数据点映射到 Canvas 像素坐标 */
export function buildLineChartLayout(
  points: LineChartInputPoint[],
  width: number,
  height: number,
): LineChartLayout {
  const pad = LINE_CHART_PADDING
  const innerW = Math.max(1, width - pad.left - pad.right)
  const innerH = Math.max(1, height - pad.top - pad.bottom)
  const n = points.length

  const coords: LineChartCoord[] = points.map((p, i) => {
    const x =
      pad.left + (n <= 1 ? innerW / 2 : (i / Math.max(1, n - 1)) * innerW)
    const clamped = Math.max(0, Math.min(100, p.value))
    const y = pad.top + innerH - (clamped / 100) * innerH
    return { x, y, value: clamped, label: p.label, tier: p.tier }
  })

  const gridY = [0, 25, 50, 75, 100].map(
    (v) => pad.top + innerH - (v / 100) * innerH,
  )

  return { width, height, coords, gridY }
}
