import { buildLineChartLayout, LINE_CHART_PADDING } from '../progressLineChartLayout'

describe('buildLineChartLayout', () => {
  it('单点居中', () => {
    const layout = buildLineChartLayout([{ value: 80, label: '5/1' }], 300, 140)
    expect(layout.coords).toHaveLength(1)
    expect(layout.coords[0].value).toBe(80)
    expect(layout.coords[0].x).toBeGreaterThan(LINE_CHART_PADDING.left)
  })

  it('多点 X 轴首尾对齐 padding', () => {
    const layout = buildLineChartLayout(
      [
        { value: 0, label: 'a' },
        { value: 100, label: 'b' },
      ],
      200,
      100,
    )
    expect(layout.coords[0].x).toBe(LINE_CHART_PADDING.left)
    expect(layout.coords[1].x).toBe(200 - LINE_CHART_PADDING.right)
    expect(layout.coords[0].y).toBeGreaterThan(layout.coords[1].y)
  })

  it('value 钳到 0–100', () => {
    const layout = buildLineChartLayout([{ value: 150, label: 'x' }], 100, 80)
    expect(layout.coords[0].value).toBe(100)
  })

  it('gridY 含 5 条水平参考线', () => {
    const layout = buildLineChartLayout([{ value: 50, label: 'm' }], 120, 90)
    expect(layout.gridY).toHaveLength(5)
  })

  // P2-W12-1：tier 必须从 input 透传到 coords，drawLineChart 才能据此切换点色
  it('透传 tier 字段（V2 报告 trust tier 着色链路）', () => {
    const layout = buildLineChartLayout(
      [
        { value: 70, label: '5/1', tier: 'high' },
        { value: 60, label: '5/2', tier: 'medium' },
        { value: 30, label: '5/3', tier: 'low' },
        { value: 80, label: '5/4' }, // V1 报告，无 tier
      ],
      400,
      120,
    )
    expect(layout.coords.map((c) => c.tier)).toEqual([
      'high',
      'medium',
      'low',
      undefined,
    ])
  })
})
