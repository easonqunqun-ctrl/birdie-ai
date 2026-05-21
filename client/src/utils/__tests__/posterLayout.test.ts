/**
 * `posterLayout` 纯函数单测（Q-C1）。
 *
 * 这些公式同时被海报 Canvas（`posterCanvas.ts`）和 React 组件（`pages/analysis/poster.tsx`）
 * 引用；一旦布局改坏，海报会偏移/出框，所以需要严格的回归保障。
 */

import {
  POSTER_HEIGHT,
  POSTER_WIDTH,
  axisLabelAnchor,
  deriveLevel,
  levelColor,
  radarPoint,
  truncateLabel,
} from '../posterLayout'

describe('posterLayout · 基础常量', () => {
  it('海报尺寸为 750×1334（@2x 竖屏）', () => {
    expect(POSTER_WIDTH).toBe(750)
    expect(POSTER_HEIGHT).toBe(1334)
  })
})

describe('posterLayout · deriveLevel 兜底', () => {
  it.each<[number | null | undefined, ReturnType<typeof deriveLevel>]>([
    [null, null],
    [undefined, null],
    [95, 'excellent'],
    [90, 'excellent'],
    [85, 'great'],
    [80, 'great'],
    [75, 'good'],
    [70, 'good'],
    [65, 'fair'],
    [60, 'fair'],
    [59, 'needs_improvement'],
    [0, 'needs_improvement'],
  ])('分数 %s → %s', (score, expected) => {
    expect(deriveLevel(score)).toBe(expected)
  })
})

describe('posterLayout · levelColor', () => {
  it('每档评级对应专属品牌色', () => {
    expect(levelColor('excellent')).toBe('#c9a227')
    expect(levelColor('great')).toBe('#1a237e')
    expect(levelColor('good')).toBe('#3b82f6')
    expect(levelColor('fair')).toBe('#f59e0b')
    expect(levelColor('needs_improvement')).toBe('#ef4444')
  })

  it('未知/空值兜底为靛蓝主色，不会落到非品牌色', () => {
    expect(levelColor(null)).toBe('#1a237e')
    expect(levelColor(undefined)).toBe('#1a237e')
  })
})

describe('posterLayout · radarPoint', () => {
  it('valueRatio=0 时所有顶点重合在中心', () => {
    const p = radarPoint(100, 100, 50, 0, 6, 0)
    expect(p.x).toBeCloseTo(100, 5)
    expect(p.y).toBeCloseTo(100, 5)
  })

  it('valueRatio=1 第 0 轴在正上方（y = centerY - radius）', () => {
    const p = radarPoint(100, 100, 50, 0, 6, 1)
    expect(p.x).toBeCloseTo(100, 5)
    expect(p.y).toBeCloseTo(50, 5)
  })

  it('valueRatio 超 1 自动钳到 [0,1]，超出半径不会跑飞', () => {
    const p = radarPoint(100, 100, 50, 0, 6, 9999)
    expect(p.y).toBeCloseTo(50, 5)
  })

  it('6 轴均匀分布：顶点距离中心始终 = radius * ratio', () => {
    for (let i = 0; i < 6; i += 1) {
      const p = radarPoint(0, 0, 100, i, 6, 0.6)
      const dist = Math.sqrt(p.x * p.x + p.y * p.y)
      expect(dist).toBeCloseTo(60, 5)
    }
  })
})

describe('posterLayout · axisLabelAnchor', () => {
  it('顶部轴标签 baseline=bottom / align=center', () => {
    const a = axisLabelAnchor(100, 100, 50, 0, 6)
    expect(a.align).toBe('center')
    expect(a.baseline).toBe('bottom')
  })

  it('右上方向轴（i=1, 60°） align=left / baseline=bottom（canvas y 向下）', () => {
    const a = axisLabelAnchor(100, 100, 50, 1, 6)
    expect(a.align).toBe('left')
    expect(a.baseline).toBe('bottom')
  })

  it('右下方向轴（i=2, 120°） align=left / baseline=top', () => {
    const a = axisLabelAnchor(100, 100, 50, 2, 6)
    expect(a.align).toBe('left')
    expect(a.baseline).toBe('top')
  })

  it('正下方轴（i=3, 180°） align=center / baseline=top', () => {
    const a = axisLabelAnchor(100, 100, 50, 3, 6)
    expect(a.align).toBe('center')
    expect(a.baseline).toBe('top')
  })

  it('左下方向轴（i=4, 240°） align=right / baseline=top', () => {
    const a = axisLabelAnchor(100, 100, 50, 4, 6)
    expect(a.align).toBe('right')
    expect(a.baseline).toBe('top')
  })

  it('左上方向轴（i=5, 300°） align=right / baseline=bottom', () => {
    const a = axisLabelAnchor(100, 100, 50, 5, 6)
    expect(a.align).toBe('right')
    expect(a.baseline).toBe('bottom')
  })
})

describe('posterLayout · truncateLabel', () => {
  it('短文本原样返回', () => {
    expect(truncateLabel('站位', 4)).toBe('站位')
  })

  it('超长文本末尾追加 …，总长度 ≤ maxChars', () => {
    const r = truncateLabel('很长很长的一句问题描述', 6)
    expect(r.length).toBe(6)
    expect(r.endsWith('…')).toBe(true)
  })

  it('maxChars=0 返回空串', () => {
    expect(truncateLabel('xxxxx', 0)).toBe('')
  })

  it('maxChars=1 不再追加 …，避免 "…" 单字符没意义', () => {
    expect(truncateLabel('xxxxx', 1)).toBe('x')
  })

  it('空 / undefined 输入安全返回空串', () => {
    expect(truncateLabel('', 5)).toBe('')
    expect(truncateLabel(undefined as unknown as string, 5)).toBe('')
  })
})
