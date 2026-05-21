/**
 * 进步曲线折线图（Canvas 2D · 小程序 weapp）
 *
 * 单序列 0–100 折线 + 网格 + 面积淡填充；无第三方图表库。
 */

import { FC, useEffect, useMemo, useState } from 'react'
import { Canvas, Text, View } from '@tarojs/components'
import Taro, { useReady } from '@tarojs/taro'
import { buildLineChartLayout } from '@/utils/progressLineChartLayout'
import {
  drawLineChart,
  LINE_CHART_COLORS,
  type LineChartCanvasContext,
} from '@/utils/progressLineChartCanvas'
import './ProgressLineChart.scss'

export interface ProgressLineChartPoint {
  value: number
  label: string
}

export interface ProgressLineChartProps {
  points: ProgressLineChartPoint[]
  /** 折线/点主色；默认靛蓝主色 */
  accentColor?: string
  canvasId?: string
}

interface CanvasNodeLike {
  width: number
  height: number
  getContext: (type: '2d') => LineChartCanvasContext & {
    scale: (x: number, y: number) => void
    fillRect: (x: number, y: number, w: number, h: number) => void
  }
}

const DEFAULT_CANVAS_ID = 'progress-line-chart'

const ProgressLineChart: FC<ProgressLineChartProps> = ({
  points,
  accentColor = LINE_CHART_COLORS.primary,
  canvasId = DEFAULT_CANVAS_ID,
}) => {
  const [ready, setReady] = useState(false)
  useReady(() => setReady(true))

  useEffect(() => {
    if (ready) return
    const t = setTimeout(() => setReady(true), 80)
    return () => clearTimeout(t)
  }, [ready])

  const layoutInput = useMemo(
    () => points.map((p) => ({ value: p.value, label: p.label })),
    [points],
  )

  useEffect(() => {
    if (!ready || layoutInput.length === 0) return
    let cancelled = false

    const draw = () => {
      const query = Taro.createSelectorQuery()
      query
        .select(`#${canvasId}`)
        .fields({ node: true, size: true })
        .exec((res) => {
          if (cancelled) return
          const wrap = res?.[0]
          const node = wrap?.node as CanvasNodeLike | undefined
          if (!node || !wrap?.width) return

          const dpr = Math.max(1, Math.min(3, Taro.getSystemInfoSync().pixelRatio || 2))
          const cssW = wrap.width
          const cssH = wrap.height || 140
          node.width = cssW * dpr
          node.height = cssH * dpr
          const ctx = node.getContext('2d')
          ctx.scale(dpr, dpr)

          const layout = buildLineChartLayout(layoutInput, cssW, cssH)
          drawLineChart(ctx, layout, accentColor)
        })
    }

    draw()
    return () => {
      cancelled = true
    }
  }, [ready, layoutInput, accentColor, canvasId])

  if (points.length === 0) {
    return (
      <View className='progress-line-chart'>
        <View className='progress-line-chart__empty'>
          <Text>暂无足够数据绘制曲线</Text>
        </View>
      </View>
    )
  }

  return (
    <View className='progress-line-chart'>
      <Canvas
        id={canvasId}
        canvasId={canvasId}
        type='2d'
        className='progress-line-chart__canvas'
      />
    </View>
  )
}

export default ProgressLineChart
