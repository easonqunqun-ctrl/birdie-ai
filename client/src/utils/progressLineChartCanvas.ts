/**
 * 进步曲线 Canvas 2D 绘制（与 progressLineChartLayout 配合）
 */

import {
  LINE_CHART_PADDING,
  type LineChartCoord,
  type LineChartLayout,
} from './progressLineChartLayout'

/** 与 app.scss 品牌 token 对齐（Canvas 不支持 CSS 变量） */
export const LINE_CHART_COLORS = {
  primary: '#1a237e',
  grid: '#e5e7eb',
  axis: '#9ca3af',
  dot: '#1a237e',
  line: '#1a237e',
  fill: 'rgba(26, 35, 126, 0.08)',
} as const

export interface LineChartCanvasContext {
  strokeStyle: string | CanvasGradient | CanvasPattern
  fillStyle: string | CanvasGradient | CanvasPattern
  font: string
  textAlign: CanvasTextAlign
  textBaseline: CanvasTextBaseline
  lineWidth: number
  globalAlpha: number
  fillRect: (x: number, y: number, w: number, h: number) => void
  beginPath: () => void
  moveTo: (x: number, y: number) => void
  lineTo: (x: number, y: number) => void
  closePath: () => void
  stroke: () => void
  fill: () => void
  arc: (
    x: number,
    y: number,
    r: number,
    startAngle: number,
    endAngle: number,
    counter?: boolean,
  ) => void
  fillText: (text: string, x: number, y: number) => void
}

export function drawLineChart(
  ctx: LineChartCanvasContext,
  layout: LineChartLayout,
  accentColor: string = LINE_CHART_COLORS.line,
): void {
  const { width, height, coords, gridY } = layout
  const pad = LINE_CHART_PADDING

  ctx.fillStyle = '#ffffff'
  ctx.fillRect(0, 0, width, height)

  ctx.strokeStyle = LINE_CHART_COLORS.grid
  ctx.lineWidth = 1
  ctx.font = '10px sans-serif'
  ctx.fillStyle = LINE_CHART_COLORS.axis
  ctx.textAlign = 'right'
  ctx.textBaseline = 'middle'

  const yLabels = [0, 25, 50, 75, 100]
  gridY.forEach((y, i) => {
    ctx.beginPath()
    ctx.moveTo(pad.left, y)
    ctx.lineTo(width - pad.right, y)
    ctx.stroke()
    ctx.fillText(String(yLabels[i]), pad.left - 6, y)
  })

  if (coords.length === 0) return

  if (coords.length >= 2) {
    ctx.fillStyle = accentColor
    ctx.globalAlpha = 0.1
    ctx.beginPath()
    ctx.moveTo(coords[0].x, coords[0].y)
    for (let i = 1; i < coords.length; i += 1) {
      ctx.lineTo(coords[i].x, coords[i].y)
    }
    ctx.lineTo(coords[coords.length - 1].x, height - pad.bottom)
    ctx.lineTo(coords[0].x, height - pad.bottom)
    ctx.closePath()
    ctx.fill()
    ctx.globalAlpha = 1
  }

  ctx.strokeStyle = accentColor
  ctx.lineWidth = 2.5
  ctx.beginPath()
  coords.forEach((c, i) => {
    if (i === 0) ctx.moveTo(c.x, c.y)
    else ctx.lineTo(c.x, c.y)
  })
  ctx.stroke()

  ctx.fillStyle = accentColor
  coords.forEach((c) => {
    ctx.beginPath()
    ctx.arc(c.x, c.y, 4, 0, Math.PI * 2)
    ctx.fill()
  })

  ctx.fillStyle = LINE_CHART_COLORS.axis
  ctx.font = '9px sans-serif'
  ctx.textAlign = 'center'
  ctx.textBaseline = 'top'
  const labelEvery = coords.length <= 8 ? 1 : Math.ceil(coords.length / 6)
  coords.forEach((c, i) => {
    if (i % labelEvery !== 0 && i !== coords.length - 1) return
    ctx.fillText(c.label, c.x, height - pad.bottom + 6)
  })
}

export function layoutToInputPoints(
  coords: LineChartCoord[],
): { value: number; label: string }[] {
  return coords.map((c) => ({ value: c.value, label: c.label }))
}
