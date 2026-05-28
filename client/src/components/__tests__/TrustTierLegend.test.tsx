/**
 * P2-W13-A · TrustTierLegend 单测.
 *
 * 关注点：
 * - hasV2Points=false → 不渲染（避免老用户在全 V1 报告下看到无意义色块）
 * - hasV2Points=true → 渲染 3 条 tier（高/中/低 + 各自一句话说明）
 * - 三个色块 className 与 ProgressLineChart 圆点 tier key 严格对齐（防止改色后图例失同步）
 */

import { render, screen } from '@testing-library/react'
import TrustTierLegend from '@/components/TrustTierLegend'

describe('TrustTierLegend', () => {
  test('hasV2Points=false 不渲染', () => {
    const { container } = render(<TrustTierLegend hasV2Points={false} />)
    expect(container.firstChild).toBeNull()
  })

  test('hasV2Points=true 渲染 3 条 tier label', () => {
    render(<TrustTierLegend hasV2Points />)
    expect(screen.getByText('曲线点颜色对应 AI 可信度')).toBeInTheDocument()
    expect(screen.getByText('高可信')).toBeInTheDocument()
    expect(screen.getByText('中等可信')).toBeInTheDocument()
    expect(screen.getByText('低可信')).toBeInTheDocument()
  })

  test('hasV2Points=true 渲染 3 条 hint 文案（防止误删 hint 列）', () => {
    render(<TrustTierLegend hasV2Points />)
    expect(screen.getByText('画面清晰、机位正、AI 看得清')).toBeInTheDocument()
    expect(screen.getByText('画面够用、可读但有些遮挡或抖动')).toBeInTheDocument()
    expect(screen.getByText('建议重拍，AI 把握不大')).toBeInTheDocument()
  })

  test('三个色块 className 必须与 ProgressLineChart Canvas tier key 对齐', () => {
    // 这条测试防止"图例上画的颜色"与"曲线点颜色"漂移：
    // SCSS 里 trust-tier-legend__dot--{key} 与 progressLineChartCanvas
    // TRUST_TIER_DOT_COLOR 共享 high/medium/low 三个 key。
    const { container } = render(<TrustTierLegend hasV2Points />)
    expect(container.querySelector('.trust-tier-legend__dot--high')).not.toBeNull()
    expect(container.querySelector('.trust-tier-legend__dot--medium')).not.toBeNull()
    expect(container.querySelector('.trust-tier-legend__dot--low')).not.toBeNull()
  })
})
