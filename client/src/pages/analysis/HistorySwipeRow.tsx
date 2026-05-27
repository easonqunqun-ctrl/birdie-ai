/**
 * 分析报告列表 · 左滑露出删除（仅 history 页使用）。
 *
 * 对比模式（compareMode）下禁用滑动，避免与点选逻辑冲突。
 */

import { FC, ReactNode, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { View, Text, type CommonEventFunction } from '@tarojs/components'
import Taro from '@tarojs/taro'

const SWIPE_DELETE_RPX = 160

type TouchPoint = { clientX: number; clientY: number }

function touchFromEvent(e: Parameters<CommonEventFunction>[0]): TouchPoint | undefined {
  const raw = e as unknown as { touches?: TouchPoint[] }
  return raw.touches?.[0]
}

function swipeActionWidthPx(): number {
  const w = Taro.getSystemInfoSync().windowWidth || 375
  return (SWIPE_DELETE_RPX / 750) * w
}

export interface HistorySwipeRowProps {
  enabled: boolean
  open: boolean
  onOpen: () => void
  onClose: () => void
  onDelete: () => void
  children: ReactNode
}

export const HistorySwipeRow: FC<HistorySwipeRowProps> = ({
  enabled,
  open,
  onOpen,
  onClose,
  onDelete,
  children,
}) => {
  const actionWidthPx = useMemo(() => swipeActionWidthPx(), [])
  const [offsetPx, setOffsetPx] = useState(0)
  const [dragging, setDragging] = useState(false)
  const touchRef = useRef({
    startX: 0,
    startY: 0,
    startOffset: 0,
    axis: 'none' as 'none' | 'x' | 'y',
  })

  const snapOffset = open ? -actionWidthPx : 0
  const displayOffset = enabled ? (dragging ? offsetPx : snapOffset) : 0

  useEffect(() => {
    if (!open) setOffsetPx(0)
  }, [open])

  const handleTouchStart = useCallback<CommonEventFunction>(
    (e) => {
      if (!enabled) return
      const t = touchFromEvent(e)
      if (!t) return
      setDragging(true)
      touchRef.current = {
        startX: t.clientX,
        startY: t.clientY,
        startOffset: open ? -actionWidthPx : offsetPx,
        axis: 'none',
      }
    },
    [enabled, open, offsetPx, actionWidthPx],
  )

  const handleTouchMove = useCallback<CommonEventFunction>(
    (e) => {
      if (!enabled) return
      const t = touchFromEvent(e)
      if (!t) return
      const dx = t.clientX - touchRef.current.startX
      const dy = t.clientY - touchRef.current.startY
      if (touchRef.current.axis === 'none') {
        if (Math.abs(dx) < 8 && Math.abs(dy) < 8) return
        touchRef.current.axis = Math.abs(dx) > Math.abs(dy) ? 'x' : 'y'
      }
      if (touchRef.current.axis !== 'x') return
      const next = touchRef.current.startOffset + dx
      setOffsetPx(Math.min(0, Math.max(-actionWidthPx, next)))
    },
    [enabled, actionWidthPx],
  )

  const handleTouchEnd = useCallback<CommonEventFunction>(() => {
    if (!enabled || touchRef.current.axis !== 'x') {
      setDragging(false)
      return
    }
    const current = offsetPx
    if (current < -actionWidthPx / 2) {
      onOpen()
    } else {
      onClose()
      setOffsetPx(0)
    }
    touchRef.current.axis = 'none'
    setDragging(false)
  }, [enabled, offsetPx, actionWidthPx, onOpen, onClose])

  if (!enabled) {
    return <View className='history__swipe-wrap'>{children}</View>
  }

  return (
    <View className='history__swipe-wrap'>
      <View className='history__swipe-actions'>
        <View
          className='history__swipe-delete'
          onClick={(ev) => {
            ev.stopPropagation()
            onDelete()
          }}
        >
          <Text>删除</Text>
        </View>
      </View>
      <View
        className='history__swipe-content'
        style={{
          transform: `translateX(${displayOffset}px)`,
          transition: dragging ? 'none' : 'transform 0.2s ease',
        }}
        onTouchStart={handleTouchStart}
        onTouchMove={handleTouchMove}
        onTouchEnd={handleTouchEnd}
        onTouchCancel={handleTouchEnd}
      >
        {children}
      </View>
    </View>
  )
}
