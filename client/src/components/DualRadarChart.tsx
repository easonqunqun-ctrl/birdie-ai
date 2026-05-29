/**
 * 双序列六维雷达（M12-05）：用户实线 + 职业参考虚线叠加同一网格。
 */

import { FC, useEffect, useState } from 'react'
import { Canvas, View, Text } from '@tarojs/components'
import Taro, { useReady } from '@tarojs/taro'

import type { RadarAxis } from './radar-chart-types'
import type { DualRadarChartProps } from './dual-radar-chart-types'

export type { DualRadarChartProps }

const CANVAS_ID = 'dual-radar-chart-canvas'
const LEVELS = 4
const PADDING = 40

const DualRadarChart: FC<DualRadarChartProps> = ({
  primaryAxes,
  secondaryAxes,
  primaryLabel = '你',
  secondaryLabel = '职业参考',
}) => {
  const [ready, setReady] = useState(false)
  useReady(() => setReady(true))
  useEffect(() => {
    if (ready) return
    const t = setTimeout(() => setReady(true), 80)
    return () => clearTimeout(t)
  }, [ready])

  useEffect(() => {
    if (!ready || primaryAxes.length === 0) return
    let cancelled = false
    let attempt = 0
    const tryDraw = () => {
      if (cancelled) return
      drawDualRadar(primaryAxes, secondaryAxes, (ok) => {
        if (cancelled) return
        if (ok) return
        attempt += 1
        if (attempt >= 3) return
        setTimeout(tryDraw, 120 * attempt)
      })
    }
    tryDraw()
    return () => {
      cancelled = true
    }
  }, [primaryAxes, secondaryAxes, ready])

  const labelPositions = computeLabelPositions(primaryAxes.length)

  return (
    <View className='dual-radar'>
      <Canvas type='2d' id={CANVAS_ID} canvasId={CANVAS_ID} className='dual-radar__canvas' />
      {primaryAxes.map((ax, i) => {
        const pos = labelPositions[i]
        return (
          <View
            key={ax.key}
            className='dual-radar__label'
            style={{ left: `${pos.x}%`, top: `${pos.y}%` }}
          >
            <Text className='dual-radar__label-name'>{ax.label}</Text>
            <Text className='dual-radar__label-score'>{ax.score}</Text>
          </View>
        )
      })}
      <View className='dual-radar__legend'>
        <View className='dual-radar__legend-item'>
          <View className='dual-radar__legend-swatch dual-radar__legend-swatch--primary' />
          <Text className='dual-radar__legend-text'>{primaryLabel}</Text>
        </View>
        <View className='dual-radar__legend-item'>
          <View className='dual-radar__legend-swatch dual-radar__legend-swatch--secondary' />
          <Text className='dual-radar__legend-text'>{secondaryLabel}</Text>
        </View>
      </View>
    </View>
  )
}

export default DualRadarChart

function drawDualRadar(
  primary: RadarAxis[],
  secondary: RadarAxis[],
  onDone?: (ok: boolean) => void,
) {
  Taro.createSelectorQuery()
    .select(`#${CANVAS_ID}`)
    .fields({ node: true, size: true })
    .exec((res) => {
      const node = res?.[0]?.node
      if (!node) {
        onDone?.(false)
        return
      }
      const canvas = node as unknown as {
        getContext: (ctxType: string) => CanvasRenderingContext2D
        width: number
        height: number
      }
      const dpr =
        (Taro.getWindowInfo?.() as { pixelRatio?: number } | undefined)?.pixelRatio ||
        Taro.getSystemInfoSync?.().pixelRatio ||
        2
      const cssW = res[0].width || 0
      const cssH = res[0].height || 0
      if (cssW <= 0 || cssH <= 0) {
        onDone?.(false)
        return
      }
      canvas.width = cssW * dpr
      canvas.height = cssH * dpr
      const ctx = canvas.getContext('2d')
      ctx.scale(dpr, dpr)

      const cx = cssW / 2
      const cy = cssH / 2
      const radius = Math.min(cssW, cssH) / 2 - PADDING
      const n = primary.length

      drawGrid(ctx, cx, cy, radius, n)
      if (secondary.length > 0) {
        drawPolygon(ctx, cx, cy, radius, secondary, {
          fill: 'rgba(201, 162, 39, 0.14)',
          stroke: '#c9a227',
          lineWidth: 2,
          dashed: true,
        })
      }
      drawPolygon(ctx, cx, cy, radius, primary, {
        fill: 'rgba(26, 35, 126, 0.28)',
        stroke: '#1a237e',
        lineWidth: 2,
        dashed: false,
      })
      onDone?.(true)
    })
}

function drawGrid(
  ctx: CanvasRenderingContext2D,
  cx: number,
  cy: number,
  radius: number,
  n: number,
) {
  ctx.strokeStyle = 'rgba(26, 35, 126, 0.18)'
  ctx.lineWidth = 1
  for (let lv = 1; lv <= LEVELS; lv++) {
    const r = (radius * lv) / LEVELS
    ctx.beginPath()
    for (let i = 0; i < n; i++) {
      const { x, y } = polarPoint(cx, cy, r, i, n)
      if (i === 0) ctx.moveTo(x, y)
      else ctx.lineTo(x, y)
    }
    ctx.closePath()
    ctx.stroke()
  }
  ctx.strokeStyle = 'rgba(26, 35, 126, 0.15)'
  for (let i = 0; i < n; i++) {
    const { x, y } = polarPoint(cx, cy, radius, i, n)
    ctx.beginPath()
    ctx.moveTo(cx, cy)
    ctx.lineTo(x, y)
    ctx.stroke()
  }
}

function drawPolygon(
  ctx: CanvasRenderingContext2D,
  cx: number,
  cy: number,
  radius: number,
  axes: RadarAxis[],
  style: { fill: string; stroke: string; lineWidth: number; dashed: boolean },
) {
  const n = axes.length
  ctx.beginPath()
  axes.forEach((ax, i) => {
    const r = (radius * Math.max(0, Math.min(100, ax.score))) / 100
    const { x, y } = polarPoint(cx, cy, r, i, n)
    if (i === 0) ctx.moveTo(x, y)
    else ctx.lineTo(x, y)
  })
  ctx.closePath()
  ctx.fillStyle = style.fill
  ctx.strokeStyle = style.stroke
  ctx.lineWidth = style.lineWidth
  if (style.dashed) ctx.setLineDash([6, 4])
  else ctx.setLineDash([])
  ctx.fill()
  ctx.stroke()
  ctx.setLineDash([])
}

function polarPoint(cx: number, cy: number, r: number, idx: number, n: number) {
  const angle = -Math.PI / 2 + (Math.PI * 2 * idx) / n
  return { x: cx + Math.cos(angle) * r, y: cy + Math.sin(angle) * r }
}

function computeLabelPositions(n: number) {
  const out: { x: number; y: number }[] = []
  const r = 48
  for (let i = 0; i < n; i++) {
    const angle = -Math.PI / 2 + (Math.PI * 2 * i) / n
    out.push({ x: 50 + Math.cos(angle) * r, y: 50 + Math.sin(angle) * r })
  }
  return out
}
