/**
 * P2-M12-08 · 骨骼线演化示意动画（best-effort · 非 AI 预测）。
 */

import { FC, useCallback, useEffect, useMemo, useState } from 'react'
import { View, Text, Canvas } from '@tarojs/components'
import Taro, { useReady } from '@tarojs/taro'
import {
  SKELETON_CONNECTIONS,
  interpolatePose,
  type PoseKeypoints,
} from '@/utils/posInterpolate'
import './SkeletonAnimation.scss'

export type EvolutionPoseState = 'user' | 'mid' | 'pro'

export interface SkeletonAnimationProps {
  start: PoseKeypoints
  end: PoseKeypoints
  caption?: string
}

const CANVAS_ID = 'skeleton-evolution-canvas'

const STATE_T: Record<EvolutionPoseState, number> = {
  user: 0,
  mid: 0.5,
  pro: 1,
}

const SkeletonAnimation: FC<SkeletonAnimationProps> = ({ start, end, caption }) => {
  const [ready, setReady] = useState(false)
  const [poseState, setPoseState] = useState<EvolutionPoseState>('user')
  const [animating, setAnimating] = useState(false)

  useReady(() => setReady(true))
  useEffect(() => {
    if (ready) return
    const t = setTimeout(() => setReady(true), 80)
    return () => clearTimeout(t)
  }, [ready])

  const pose = useMemo(
    () => interpolatePose(start, end, STATE_T[poseState]),
    [start, end, poseState],
  )

  const draw = useCallback(() => {
    if (!ready) return
    Taro.createSelectorQuery()
      .select(`#${CANVAS_ID}`)
      .fields({ node: true, size: true })
      .exec((res) => {
        const node = res?.[0]?.node
        if (!node) return
        const canvas = node as unknown as {
          getContext: (ctxType: string) => CanvasRenderingContext2D
          width: number
          height: number
        }
        const dpr =
          (Taro.getWindowInfo?.() as { pixelRatio?: number } | undefined)?.pixelRatio ||
          Taro.getSystemInfoSync?.().pixelRatio ||
          2
        const cssW = res[0].width || 280
        const cssH = res[0].height || 220
        canvas.width = cssW * dpr
        canvas.height = cssH * dpr
        const ctx = canvas.getContext('2d')
        ctx.scale(dpr, dpr)
        ctx.clearRect(0, 0, cssW, cssH)
        ctx.fillStyle = '#f5f6fa'
        ctx.fillRect(0, 0, cssW, cssH)

        const pad = 24
        const toCanvas = (p: { x: number; y: number }) => ({
          x: pad + p.x * (cssW - pad * 2),
          y: pad + p.y * (cssH - pad * 2),
        })

        ctx.strokeStyle = '#1a237e'
        ctx.lineWidth = 3
        ctx.lineCap = 'round'
        for (const [a, b] of SKELETON_CONNECTIONS) {
          if (a >= pose.length || b >= pose.length) continue
          const p1 = toCanvas(pose[a])
          const p2 = toCanvas(pose[b])
          ctx.beginPath()
          ctx.moveTo(p1.x, p1.y)
          ctx.lineTo(p2.x, p2.y)
          ctx.stroke()
        }

        ctx.fillStyle = '#c9a227'
        for (const pt of pose) {
          const c = toCanvas(pt)
          ctx.beginPath()
          ctx.arc(c.x, c.y, 4, 0, Math.PI * 2)
          ctx.fill()
        }
      })
  }, [pose, ready])

  useEffect(() => {
    draw()
  }, [draw])

  const runTween = () => {
    if (animating) return
    setAnimating(true)
    setPoseState('user')
    const steps = [0, 0.25, 0.5, 0.75, 1] as const
    let i = 0
    const tick = () => {
      const t = steps[i]
      if (t === 0) setPoseState('user')
      else if (t === 0.5) setPoseState('mid')
      else if (t === 1) setPoseState('pro')
      i += 1
      if (i >= steps.length) {
        setAnimating(false)
        return
      }
      setTimeout(tick, 600)
    }
    setTimeout(tick, 600)
  }

  return (
    <View className='skeleton-anim'>
      {caption ? <Text className='skeleton-anim__caption'>{caption}</Text> : null}
      <Text className='skeleton-anim__disclaimer'>
        示意动画，非 AI 逐帧预测；仅帮助理解「追平差距」的方向。
      </Text>
      <Canvas
        type='2d'
        id={CANVAS_ID}
        canvasId={CANVAS_ID}
        className='skeleton-anim__canvas'
      />
      <View className='skeleton-anim__states'>
        {(
          [
            ['user', '你的现状'],
            ['mid', '中间态'],
            ['pro', '职业目标'],
          ] as const
        ).map(([key, label]) => (
          <View
            key={key}
            className={[
              'skeleton-anim__state',
              poseState === key ? 'skeleton-anim__state--active' : '',
            ]
              .filter(Boolean)
              .join(' ')}
            onClick={() => !animating && setPoseState(key)}
          >
            <Text>{label}</Text>
          </View>
        ))}
      </View>
      <View className='skeleton-anim__play' onClick={() => void runTween()}>
        <Text>{animating ? '播放中…' : '播放演化'}</Text>
      </View>
    </View>
  )
}

export default SkeletonAnimation
