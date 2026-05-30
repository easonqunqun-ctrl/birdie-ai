import { computeLabelPositions } from '@/utils/radarLabelLayout'

describe('radarLabelLayout', () => {
  test('六轴时六个顶点均在容器内', () => {
    const pts = computeLabelPositions(6)
    expect(pts).toHaveLength(6)
    for (const p of pts) {
      expect(p.x).toBeGreaterThanOrEqual(2)
      expect(p.x).toBeLessThanOrEqual(98)
      expect(p.y).toBeGreaterThanOrEqual(2)
      expect(p.y).toBeLessThanOrEqual(96)
    }
  })

  test('正上顶点 y 不会贴顶裁切', () => {
    const pts = computeLabelPositions(6)
    expect(pts[0].y).toBeGreaterThan(4)
  })

  test('正下顶点为六轴 index 3', () => {
    const pts = computeLabelPositions(6)
    expect(pts[3].y).toBeLessThan(94)
  })
})
