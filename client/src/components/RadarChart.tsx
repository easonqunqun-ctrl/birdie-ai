/**
 * 六维挥杆雷达图组件
 *
 * 设计目标：
 *   - 不引入第三方图表库（避免 ECharts 小程序版 200KB+ 的包体膨胀）
 *   - 只在小程序 Canvas 2d 上手绘；H5 / 其他端暂不适配（MVP 仅 weapp）
 *   - 顶点文字标签用 DOM `<View>` 层绝对定位，避免 Canvas 跨端字体问题，也顺便
 *     把"点击顶点跳帧"做成常规 onClick 事件
 *
 * 使用约束：
 *   - 小程序新 Canvas 2d 需要在 `useReady` 之后通过 `createSelectorQuery` 取 node
 *   - 父组件必须给容器一个固定高度（默认 480rpx），否则 `fields({ size: true })`
 *     拿到的 height 可能为 0
 */

import { FC, useEffect, useRef, useState } from 'react'
import { Canvas, View, Text } from '@tarojs/components'
import Taro, { useReady } from '@tarojs/taro'

/** 雷达图一个轴的数据点 */
export interface RadarAxis {
  key: string
  /** 轴标签（显示在顶点外侧） */
  label: string
  /** 分数（0-100） */
  score: number
  /** 是否为弱项（高亮色） */
  is_weakest?: boolean
}

export interface RadarChartProps {
  axes: RadarAxis[]
  /** 点击顶点（或顶点标签）回调 */
  onTapAxis?: (key: string) => void
  /** Canvas 内部坐标像素；不同于 rpx。默认 300 × 300，适配 750rpx 屏约 600rpx */
  size?: number
}

const CANVAS_ID = 'radar-chart-canvas'
const LEVELS = 4 // 网格层数（25 / 50 / 75 / 100）
const PADDING = 40 // Canvas 四周留白（像素）

const RadarChart: FC<RadarChartProps> = ({ axes, onTapAxis, size = 300 }) => {
  const [ready, setReady] = useState(false)
  const canvasSizeRef = useRef<{ w: number; h: number }>({ w: size, h: size })

  // Canvas 节点只取一次，绘制依赖 axes 变化时重绘
  useReady(() => setReady(true))

  useEffect(() => {
    if (!ready) return
    drawRadar(axes, canvasSizeRef.current.w, canvasSizeRef.current.h)
    // 仅在 axes 数据变化时重绘
  }, [axes, ready])

  /** 顶点标签的屏幕坐标（百分比，相对容器） */
  const labelPositions = computeLabelPositions(axes.length)

  return (
    <View className='radar' style={{ '--radar-size': `${size * 2}rpx` } as React.CSSProperties}>
      <Canvas
        type='2d'
        id={CANVAS_ID}
        canvasId={CANVAS_ID}
        className='radar__canvas'
        style={{ width: `${size * 2}rpx`, height: `${size * 2}rpx` }}
      />
      {axes.map((ax, i) => {
        const pos = labelPositions[i]
        return (
          <View
            key={ax.key}
            className={[
              'radar__label',
              ax.is_weakest ? 'radar__label--weakest' : '',
            ]
              .filter(Boolean)
              .join(' ')}
            style={{ left: `${pos.x}%`, top: `${pos.y}%` }}
            onClick={() => onTapAxis?.(ax.key)}
          >
            <Text className='radar__label-name'>{ax.label}</Text>
            <Text className='radar__label-score'>{ax.score}</Text>
          </View>
        )
      })}
    </View>
  )
}

export default RadarChart

// =====================================================================
// Canvas 绘制核心
// =====================================================================
function drawRadar(axes: RadarAxis[], targetW: number, targetH: number) {
  Taro.createSelectorQuery()
    .select(`#${CANVAS_ID}`)
    .fields({ node: true, size: true })
    .exec((res) => {
      if (!res || !res[0] || !res[0].node) return
      const canvas = res[0].node as unknown as {
        getContext: (ctxType: string) => CanvasRenderingContext2D
        width: number
        height: number
      }
      // 按 DPR 放大绘图分辨率，避免小程序上模糊
      const dpr = Taro.getSystemInfoSync().pixelRatio || 2
      const cssW = res[0].width || targetW
      const cssH = res[0].height || targetH
      canvas.width = cssW * dpr
      canvas.height = cssH * dpr
      const ctx = canvas.getContext('2d')
      ctx.scale(dpr, dpr)

      const cx = cssW / 2
      const cy = cssH / 2
      const radius = Math.min(cssW, cssH) / 2 - PADDING
      const n = axes.length

      // 1) 底层网格（4 层正多边形 + 中心放射线）
      ctx.strokeStyle = 'rgba(26, 74, 59, 0.18)'
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
      // 放射线
      ctx.strokeStyle = 'rgba(26, 74, 59, 0.15)'
      for (let i = 0; i < n; i++) {
        const { x, y } = polarPoint(cx, cy, radius, i, n)
        ctx.beginPath()
        ctx.moveTo(cx, cy)
        ctx.lineTo(x, y)
        ctx.stroke()
      }

      // 2) 分数多边形（填充 + 描边）
      ctx.beginPath()
      axes.forEach((ax, i) => {
        const r = (radius * Math.max(0, Math.min(100, ax.score))) / 100
        const { x, y } = polarPoint(cx, cy, r, i, n)
        if (i === 0) ctx.moveTo(x, y)
        else ctx.lineTo(x, y)
      })
      ctx.closePath()
      ctx.fillStyle = 'rgba(26, 74, 59, 0.35)' // primary 带透明
      ctx.strokeStyle = '#1a4a3b'
      ctx.lineWidth = 2
      ctx.fill()
      ctx.stroke()

      // 3) 各顶点的小圆点（弱项高亮金色）
      axes.forEach((ax, i) => {
        const r = (radius * Math.max(0, Math.min(100, ax.score))) / 100
        const { x, y } = polarPoint(cx, cy, r, i, n)
        ctx.beginPath()
        ctx.arc(x, y, ax.is_weakest ? 6 : 4, 0, Math.PI * 2)
        ctx.fillStyle = ax.is_weakest ? '#c9a227' : '#1a4a3b'
        ctx.fill()
        if (ax.is_weakest) {
          ctx.strokeStyle = '#ffffff'
          ctx.lineWidth = 2
          ctx.stroke()
        }
      })
    })
}

function polarPoint(cx: number, cy: number, r: number, idx: number, n: number) {
  // 顶部为 0°（-Math.PI/2），顺时针分布
  const angle = -Math.PI / 2 + (Math.PI * 2 * idx) / n
  return {
    x: cx + Math.cos(angle) * r,
    y: cy + Math.sin(angle) * r,
  }
}

/** DOM 层顶点标签的百分比坐标（相对容器） */
function computeLabelPositions(n: number) {
  const out: { x: number; y: number }[] = []
  // 让标签比雷达边再往外 8%（保证不盖住雷达边线）
  const r = 54
  for (let i = 0; i < n; i++) {
    const angle = -Math.PI / 2 + (Math.PI * 2 * i) / n
    out.push({
      x: 50 + Math.cos(angle) * r,
      y: 50 + Math.sin(angle) * r,
    })
  }
  return out
}
