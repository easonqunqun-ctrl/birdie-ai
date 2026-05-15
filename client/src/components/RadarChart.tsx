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
 *   - 父组件 .report__section 已经给了 padding，雷达图容器自身用 padding-top: 100%
 *     trick 强制正方形，CSS 层面对调用方零要求
 */

import { FC, useEffect, useState } from 'react'
import { Canvas, View, Text } from '@tarojs/components'
import Taro, { useReady } from '@tarojs/taro'

import type { RadarAxis, RadarChartProps } from './radar-chart-types'

export type { RadarAxis, RadarChartProps }

const CANVAS_ID = 'radar-chart-canvas'
const LEVELS = 4 // 网格层数（25 / 50 / 75 / 100）
const PADDING = 40 // Canvas 四周留白（像素）

const RadarChart: FC<RadarChartProps> = ({ axes, onTapAxis }) => {
  /**
   * `ready` 双触发：
   *   - useReady：page 首次 onReady 时 set true（首次进入报告页有效）
   *   - useEffect setTimeout 80ms：fallback，覆盖"组件被异步渲染（report 数据
   *     fetch 完成后才挂载 RadarChart）→ 此时 page 早已 onReady 过，useReady
   *     回调不会再触发"的场景。两条路径只要任何一条触发，drawRadar 就开跑。
   */
  const [ready, setReady] = useState(false)
  useReady(() => setReady(true))
  useEffect(() => {
    if (ready) return
    const t = setTimeout(() => setReady(true), 80)
    return () => clearTimeout(t)
  }, [ready])

  useEffect(() => {
    if (!ready || axes.length === 0) return
    /**
     * Canvas 2d 节点 mount 后 selectorQuery 不一定立刻拿得到 node，
     * 在低端机或 webview 升级后偶发为 null。带最多 3 次重试 + 指数退避
     * （0ms / 120ms / 360ms），命中率经验值 > 99%。
     */
    let cancelled = false
    let attempt = 0
    const tryDraw = () => {
      if (cancelled) return
      drawRadar(axes, (ok) => {
        if (cancelled) return
        if (ok) return
        attempt += 1
        if (attempt >= 3) {
          console.warn('[RadarChart] canvas node 取不到，已重试 3 次仍失败')
          return
        }
        setTimeout(tryDraw, 120 * attempt)
      })
    }
    tryDraw()
    return () => {
      cancelled = true
    }
  }, [axes, ready])

  /** 顶点标签的屏幕坐标（百分比，相对容器） */
  const labelPositions = computeLabelPositions(axes.length)

  return (
    <View className='radar'>
      {/**
       * Canvas 不再 inline 写死宽高，而是 className 走 padding-top 撑出来的
       * absolute fill。inline 写死 600rpx 会 override CSS 100%，在某些低端机
       * 上反而触发 0 高度（容器实际能给的高度算到不一样）。绘图分辨率以
       * selectorQuery 取到的实际 css 尺寸 × dpr 为准。
       */}
      <Canvas
        type='2d'
        id={CANVAS_ID}
        canvasId={CANVAS_ID}
        className='radar__canvas'
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
/**
 * @param onDone 绘制成功 → ok=true；node 取不到（需要外层重试）→ ok=false
 */
function drawRadar(axes: RadarAxis[], onDone?: (ok: boolean) => void) {
  Taro.createSelectorQuery()
    .select(`#${CANVAS_ID}`)
    .fields({ node: true, size: true })
    .exec((res) => {
      const node = res?.[0]?.node
      if (!node) {
        // selectorQuery 在某些低端机上首次会返回 null，让外层走重试
        onDone?.(false)
        return
      }
      const canvas = node as unknown as {
        getContext: (ctxType: string) => CanvasRenderingContext2D
        width: number
        height: number
      }
      // 按 DPR 放大绘图分辨率，避免小程序上模糊。
      // getSystemInfoSync 在新基础库 deprecated，优先用 getWindowInfo；
      // 都拿不到时兜底 dpr = 2（iOS Retina 通用值，避免 NaN/0）
      const dpr =
        (Taro.getWindowInfo?.() as { pixelRatio?: number } | undefined)?.pixelRatio ||
        Taro.getSystemInfoSync?.().pixelRatio ||
        2
      const cssW = res[0].width || 0
      const cssH = res[0].height || 0
      if (cssW <= 0 || cssH <= 0) {
        // 容器塌了 → 上层 .radar 高度为 0，画了也看不见，避免静默 NaN
        console.warn('[RadarChart] canvas 容器尺寸为 0，跳过绘制', { cssW, cssH })
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
      const n = axes.length

      // 1) 底层网格（4 层正多边形 + 中心放射线）
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
      // 放射线
      ctx.strokeStyle = 'rgba(26, 35, 126, 0.15)'
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
      ctx.fillStyle = 'rgba(26, 35, 126, 0.32)' // 主色带透明
      ctx.strokeStyle = '#1a237e'
      ctx.lineWidth = 2
      ctx.fill()
      ctx.stroke()

      // 3) 各顶点的小圆点（弱项高亮金色）
      axes.forEach((ax, i) => {
        const r = (radius * Math.max(0, Math.min(100, ax.score))) / 100
        const { x, y } = polarPoint(cx, cy, r, i, n)
        ctx.beginPath()
        ctx.arc(x, y, ax.is_weakest ? 6 : 4, 0, Math.PI * 2)
        ctx.fillStyle = ax.is_weakest ? '#c9a227' : '#1a237e'
        ctx.fill()
        if (ax.is_weakest) {
          ctx.strokeStyle = '#ffffff'
          ctx.lineWidth = 2
          ctx.stroke()
        }
      })
      onDone?.(true)
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

/**
 * DOM 层顶点标签的百分比坐标（相对容器）。
 *
 * r 值历史教训：原值 54 会让 i=3（底部 downswing）的 label 落到 y=104%，
 * 直接被 .radar 容器（aspect-ratio square）下边缘裁掉，6 个轴只能看到 5 个。
 * 现在锁到 48：再大的 label 也保证 ≤ 100% 留在容器内；canvas 的 PADDING=40
 * 已经把绘制区压缩到 80% 半径，留下的 20% 给 label 浮在多边形外侧足够。
 */
function computeLabelPositions(n: number) {
  const out: { x: number; y: number }[] = []
  const r = 48
  for (let i = 0; i < n; i++) {
    const angle = -Math.PI / 2 + (Math.PI * 2 * i) / n
    out.push({
      x: 50 + Math.cos(angle) * r,
      y: 50 + Math.sin(angle) * r,
    })
  }
  return out
}
