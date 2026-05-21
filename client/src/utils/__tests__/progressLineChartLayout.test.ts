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
})
