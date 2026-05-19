/**
 * RadarChart.tsx 单测：DOM 层（顶点标签 + 点击事件）
 *
 * Canvas 绘制无法在 jsdom 里验证（@tarojs/components 的 <Canvas> 被 stub 成空 <canvas>），
 * 这里只验证 DOM 层的可测部分：
 *   - 渲染 N 个顶点标签
 *   - is_weakest 加上 --weakest 修饰类
 *   - 点击顶点触发 onTapAxis(key)
 */

import * as React from 'react'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import RadarChart from '@/components/RadarChart'
import type { RadarAxis } from '@/components/radar-chart-types'

afterEach(cleanup)

const AXES: RadarAxis[] = [
  { key: 'plane', label: '平面性', score: 80 },
  { key: 'tempo', label: '节奏', score: 70, is_weakest: true },
  { key: 'rotation', label: '转体', score: 90 },
  { key: 'downswing', label: '下杆', score: 60 },
  { key: 'impact', label: '触球', score: 75 },
  { key: 'follow', label: '随挥', score: 85 },
]

describe('RadarChart · DOM', () => {
  test('渲染六个顶点标签', () => {
    render(<RadarChart axes={AXES} />)
    for (const ax of AXES) {
      expect(screen.getByText(ax.label)).toBeInTheDocument()
      expect(screen.getByText(String(ax.score))).toBeInTheDocument()
    }
  })

  test('is_weakest=true 的标签带 radar__label--weakest 修饰类', () => {
    const { container } = render(<RadarChart axes={AXES} />)
    const weakest = container.querySelector('.radar__label--weakest')
    expect(weakest).not.toBeNull()
    expect(weakest!.textContent).toContain('节奏')
  })

  test('axes 为空时 → 不渲染 label，但根容器仍在', () => {
    const { container } = render(<RadarChart axes={[]} />)
    expect(container.querySelectorAll('.radar__label').length).toBe(0)
    expect(container.querySelector('.radar')).not.toBeNull()
  })

  test('点击顶点触发 onTapAxis(key)', async () => {
    const onTapAxis = jest.fn()
    render(<RadarChart axes={AXES} onTapAxis={onTapAxis} />)
    const user = userEvent.setup()
    await user.click(screen.getByText('转体'))
    expect(onTapAxis).toHaveBeenCalledWith('rotation')
  })

  test('onTapAxis 未传时点击不抛错', async () => {
    render(<RadarChart axes={AXES} />)
    const user = userEvent.setup()
    await user.click(screen.getByText('触球'))
    // 没抛错就是通过
  })

  test('label 顶点数与 axes 长度一致（任意 N）', () => {
    const four: RadarAxis[] = AXES.slice(0, 4)
    const { container } = render(<RadarChart axes={four} />)
    expect(container.querySelectorAll('.radar__label').length).toBe(4)
  })
})
