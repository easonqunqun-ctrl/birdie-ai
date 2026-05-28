/**
 * 机位友好警示 banner（P2-W14-B）
 *
 * 把 W13-B 让 `_enrich_v2` 真正生成的 `camera_angle_mismatch` 和 W12-2 落地的
 * `camera_angle_large_offset` 两个 engine_warning 翻译成**普通用户能看懂**的话。
 *
 * 设计要点
 * --------
 * - 仅当 engine_warnings 里含至少一条 angle 相关 warning 才渲染
 * - **不**重复 debug 浮层里的 raw code/detail——那是给 PM/教研的；本组件给 C 端
 *   用户的就一句话："下次拍的时候这样做"
 * - mismatch + large_offset 同时存在时合并为一条 banner（不堆两块占屏）
 * - mismatch 文案带上"你声明的"和"AI 看到的"两个具体机位，比泛泛"机位不对"具体
 * - 不阻塞用户看报告（仅 info 级 banner，不弹窗）
 * - 用 amber/warn 配色（不是 error 红，不吓人）
 *
 * 与现有组件的关系
 * ---------------
 * - 位置：report.tsx 在 TrustBadge 下方、qualityWarningLines 上方
 *   (TrustBadge 已经传达"整体可信度"；本 banner 解释"为什么可信度偏低"中的一种原因)
 * - debug 浮层（W10）仍然存在，只是给能看 raw code 的人
 */

import { FC, useMemo } from 'react'
import { Text, View } from '@tarojs/components'
import { CAMERA_ANGLE_LABEL, type EngineWarning } from '@/types/analysis'
import type { CameraAngle } from '@/types/api'
import './CameraAngleAlert.scss'

export interface CameraAngleAlertProps {
  /** 当前报告的 engine_warnings（V1 报告或老报告传 null/undefined 都安全） */
  engineWarnings?: EngineWarning[] | null
  /** 用户声明的机位（report.camera_angle）；用于在 mismatch 文案里点名 */
  declaredCameraAngle?: CameraAngle | null
}

const ANGLE_DESC: Record<string, string> = {
  face_on: '正面（Face-On）',
  down_the_line: '侧面（Down-the-Line）',
  unknown: '未知机位',
}

const _resolveDetectedAngle = (detail: string | null | undefined): string | null => {
  // detail 形如 "declared=face_on detected=down_the_line confidence=0.82"
  // （W12-2 camera_angle.angle_engine_warnings 的输出格式）
  if (!detail) return null
  const m = detail.match(/detected=([a-z_]+)/)
  return m ? m[1] : null
}

const _resolveOffsetDeg = (detail: string | null | undefined): number | null => {
  if (!detail) return null
  const m = detail.match(/offset_deg=([0-9]+(?:\.[0-9]+)?)/)
  return m ? Number(m[1]) : null
}

const CameraAngleAlert: FC<CameraAngleAlertProps> = ({
  engineWarnings,
  declaredCameraAngle,
}) => {
  const lines = useMemo<string[]>(() => {
    if (!engineWarnings || engineWarnings.length === 0) return []
    const out: string[] = []

    const mismatch = engineWarnings.find((w) => w.code === 'camera_angle_mismatch')
    if (mismatch) {
      const detectedKey = _resolveDetectedAngle(mismatch.detail)
      const declaredLabel = declaredCameraAngle
        ? CAMERA_ANGLE_LABEL[declaredCameraAngle]
        : null
      const detectedLabel = detectedKey ? ANGLE_DESC[detectedKey] || detectedKey : null
      if (declaredLabel && detectedLabel) {
        out.push(
          `你选的是「${declaredLabel}」，AI 看到的画面更像「${detectedLabel}」。下次按你选的机位摆手机，分析会更准。`,
        )
      } else {
        out.push('AI 看到的机位与你选的不一致，下次按选项摆好机位会更准。')
      }
    }

    const largeOffset = engineWarnings.find((w) => w.code === 'camera_angle_large_offset')
    if (largeOffset) {
      const deg = _resolveOffsetDeg(largeOffset.detail)
      if (deg !== null && Number.isFinite(deg)) {
        out.push(
          `镜头偏角约 ${deg.toFixed(0)}°（>15°），AI 把握不大；把手机摆正一些下次更稳。`,
        )
      } else {
        out.push('镜头有点歪（偏角 >15°），把手机摆正一些下次更稳。')
      }
    }

    return out
  }, [engineWarnings, declaredCameraAngle])

  if (lines.length === 0) return null

  return (
    <View className='camera-angle-alert' role='alert'>
      <View className='camera-angle-alert__head'>
        <Text className='camera-angle-alert__icon'>📷</Text>
        <Text className='camera-angle-alert__title'>机位提示</Text>
      </View>
      <View className='camera-angle-alert__body'>
        {lines.map((line, i) => (
          <Text key={i} className='camera-angle-alert__line'>
            {line}
          </Text>
        ))}
      </View>
    </View>
  )
}

export default CameraAngleAlert
