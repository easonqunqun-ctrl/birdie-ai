/**
 * P2-W14-B · CameraAngleAlert 单测.
 *
 * 覆盖：
 * - 空 engine_warnings / V1 报告 → 不渲染（避免老用户看到无意义 banner）
 * - 仅 mismatch → 一行 + 含 declared/detected 中文文案
 * - 仅 large_offset → 一行 + 含偏角数字
 * - mismatch + large_offset 共存 → 两行合并到同一个 banner（不堆两块）
 * - detail 缺失或解析失败 → 兜底文案（不崩 + 不显示乱码）
 */

import { render, screen } from '@testing-library/react'
import CameraAngleAlert from '@/components/CameraAngleAlert'
import type { EngineWarning } from '@/types/analysis'

const mismatch: EngineWarning = {
  code: 'camera_angle_mismatch',
  level: 'info',
  detail: 'detected=down_the_line != declared=face_on; conf=0.82',
}

const largeOffset: EngineWarning = {
  code: 'camera_angle_large_offset',
  level: 'warn',
  detail: 'offset_deg=18.5 > 15.0; detected=down_the_line',
}

const otherWarning: EngineWarning = {
  code: 'codec_unsupported',
  level: 'warn',
  detail: 'codec=hevc',
}

describe('CameraAngleAlert', () => {
  test('engine_warnings 为 null → 不渲染（V1 报告兜底）', () => {
    const { container } = render(
      <CameraAngleAlert engineWarnings={null} declaredCameraAngle='face_on' />,
    )
    expect(container.firstChild).toBeNull()
  })

  test('engine_warnings 为 [] → 不渲染', () => {
    const { container } = render(
      <CameraAngleAlert engineWarnings={[]} declaredCameraAngle='face_on' />,
    )
    expect(container.firstChild).toBeNull()
  })

  test('engine_warnings 含其它 code 但无 angle → 不渲染', () => {
    const { container } = render(
      <CameraAngleAlert
        engineWarnings={[otherWarning]}
        declaredCameraAngle='face_on'
      />,
    )
    expect(container.firstChild).toBeNull()
  })

  test('仅 mismatch → 渲染 banner + 含 declared+detected 中文', () => {
    render(
      <CameraAngleAlert
        engineWarnings={[mismatch]}
        declaredCameraAngle='face_on'
      />,
    )
    expect(screen.getByText('机位提示')).toBeInTheDocument()
    // 必须明确说出"你选的是正面（Face-On）"和"AI 看到的更像侧面（Down-the-Line）"
    expect(
      screen.getByText(/你选的是「正面（Face-On）」.*AI 看到的画面更像「侧面（Down-the-Line）」/),
    ).toBeInTheDocument()
  })

  test('mismatch detail 缺失 → 走兜底文案不崩', () => {
    const broken: EngineWarning = {
      code: 'camera_angle_mismatch',
      level: 'info',
      detail: null,
    }
    render(
      <CameraAngleAlert engineWarnings={[broken]} declaredCameraAngle='face_on' />,
    )
    expect(screen.getByText('机位提示')).toBeInTheDocument()
    expect(
      screen.getByText('AI 看到的机位与你选的不一致，下次按选项摆好机位会更准。'),
    ).toBeInTheDocument()
  })

  test('仅 large_offset → 渲染 + 含偏角整数度数（18°）', () => {
    render(
      <CameraAngleAlert
        engineWarnings={[largeOffset]}
        declaredCameraAngle='face_on'
      />,
    )
    expect(screen.getByText(/镜头偏角约 19°/)).toBeInTheDocument() // 18.5 round → 19
  })

  test('large_offset detail 解析不到度数 → 走兜底文案', () => {
    const broken: EngineWarning = {
      code: 'camera_angle_large_offset',
      level: 'warn',
      detail: '???',
    }
    render(
      <CameraAngleAlert engineWarnings={[broken]} declaredCameraAngle='face_on' />,
    )
    expect(
      screen.getByText('镜头有点歪（偏角 >15°），把手机摆正一些下次更稳。'),
    ).toBeInTheDocument()
  })

  test('mismatch + large_offset 共存 → 同一个 banner 两行（不堆两块 head）', () => {
    const { container } = render(
      <CameraAngleAlert
        engineWarnings={[mismatch, largeOffset]}
        declaredCameraAngle='face_on'
      />,
    )
    // 只有一个 banner head
    const heads = container.querySelectorAll('.camera-angle-alert__head')
    expect(heads.length).toBe(1)
    // 但 body 里有两行
    const lines = container.querySelectorAll('.camera-angle-alert__line')
    expect(lines.length).toBe(2)
  })

  test('declared 与 detected 相等（不应触发 mismatch，但容错传进来）→ 中文文案仍出（不抛错）', () => {
    const weird: EngineWarning = {
      code: 'camera_angle_mismatch',
      level: 'info',
      detail: 'detected=face_on != declared=face_on; conf=0.95',
    }
    render(
      <CameraAngleAlert engineWarnings={[weird]} declaredCameraAngle='face_on' />,
    )
    // 不期望 throw；语义虽然奇怪但 UI 不能崩
    expect(screen.getByText('机位提示')).toBeInTheDocument()
  })
})
