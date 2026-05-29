/**
 * P2-W16-B / D · ScorePercentileCard 单测.
 *
 * 关注点
 * ======
 * - data=null → 整卡不渲染（loading / 错误兜底，父组件不渲染时不出空格）
 * - percentile=null → 整卡不渲染（cohort_size<5 服务端约定）
 * - user_score=null → 整卡不渲染（用户没有同 club_type 完成态分析）
 * - 正常态 → 渲染 4 条信息（百分位 / cohort_label / user_score / median）
 * - 颜色梯度：≥75 金 / ≥50 主色 / <50 灰
 * - rightSlot 透传（父组件可挂 club_type 切换器）
 */

import { render, screen } from '@testing-library/react'
import ScorePercentileCard, {
  type ScorePercentileData,
} from '@/components/ScorePercentileCard'

const baseData: ScorePercentileData = {
  user_score: 85,
  percentile: 73,
  cohort_size: 23,
  cohort_label: '中级 / 七号铁',
  median: 72,
  club_type: 'iron_7',
  golf_level: 'intermediate',
  computed_at: '2026-05-29T08:00:00Z',
}

describe('ScorePercentileCard · 不渲染分支（避免误导）', () => {
  test('data=null → 整卡不渲染', () => {
    const { container } = render(<ScorePercentileCard data={null} />)
    expect(container.firstChild).toBeNull()
  })

  test('percentile=null（cohort_size<5 服务端兜底）→ 整卡不渲染', () => {
    const data = { ...baseData, percentile: null, median: null, cohort_size: 3 }
    const { container } = render(<ScorePercentileCard data={data} />)
    expect(container.firstChild).toBeNull()
  })

  test('user_score=null（用户没同 club_type 完成态分析）→ 整卡不渲染', () => {
    const data = { ...baseData, user_score: null }
    const { container } = render(<ScorePercentileCard data={data} />)
    expect(container.firstChild).toBeNull()
  })
})

describe('ScorePercentileCard · 正常态渲染', () => {
  test('渲染 4 条核心信息', () => {
    render(<ScorePercentileCard data={baseData} />)
    expect(screen.getByText('同水平对比')).toBeInTheDocument()
    expect(screen.getByText('73%')).toBeInTheDocument()
    expect(screen.getByText('击败 73% 中级 / 七号铁')).toBeInTheDocument()
    expect(screen.getByText('你')).toBeInTheDocument()
    expect(screen.getByText('85')).toBeInTheDocument()
    expect(screen.getByText('群体中位')).toBeInTheDocument()
    expect(screen.getByText('72')).toBeInTheDocument()
    expect(screen.getByText('样本')).toBeInTheDocument()
    expect(screen.getByText('23')).toBeInTheDocument()
  })

  test('percentile=0 边界（"只击败 0%" 仍真实展示，不能藏）', () => {
    const data = { ...baseData, percentile: 0 }
    render(<ScorePercentileCard data={data} />)
    expect(screen.getByText('0%')).toBeInTheDocument()
  })

  test('percentile=100 边界（满分击败全员）', () => {
    const data = { ...baseData, percentile: 100 }
    render(<ScorePercentileCard data={data} />)
    expect(screen.getByText('100%')).toBeInTheDocument()
  })
})

describe('ScorePercentileCard · 颜色梯度', () => {
  test('percentile ≥ 75 → gold tone', () => {
    const data = { ...baseData, percentile: 75 }
    const { container } = render(<ScorePercentileCard data={data} />)
    expect(
      container.querySelector('.score-percentile-card__pct--gold'),
    ).not.toBeNull()
    expect(
      container.querySelector('.score-percentile-card__pct--primary'),
    ).toBeNull()
  })

  test('percentile in [50, 75) → primary tone', () => {
    const data = { ...baseData, percentile: 50 }
    const { container } = render(<ScorePercentileCard data={data} />)
    expect(
      container.querySelector('.score-percentile-card__pct--primary'),
    ).not.toBeNull()
    expect(
      container.querySelector('.score-percentile-card__pct--gold'),
    ).toBeNull()
  })

  test('percentile < 50 → muted tone（不鼓励"刚击败 5%"误读）', () => {
    const data = { ...baseData, percentile: 30 }
    const { container } = render(<ScorePercentileCard data={data} />)
    expect(
      container.querySelector('.score-percentile-card__pct--muted'),
    ).not.toBeNull()
    expect(
      container.querySelector('.score-percentile-card__pct--gold'),
    ).toBeNull()
  })

  test('percentile=74 → 仍是 primary（边界严格）', () => {
    const data = { ...baseData, percentile: 74 }
    const { container } = render(<ScorePercentileCard data={data} />)
    expect(
      container.querySelector('.score-percentile-card__pct--primary'),
    ).not.toBeNull()
  })

  test('percentile=49 → muted（边界严格）', () => {
    const data = { ...baseData, percentile: 49 }
    const { container } = render(<ScorePercentileCard data={data} />)
    expect(
      container.querySelector('.score-percentile-card__pct--muted'),
    ).not.toBeNull()
  })
})

describe('ScorePercentileCard · rightSlot 透传', () => {
  test('rightSlot 渲染在头部右侧', () => {
    render(
      <ScorePercentileCard
        data={baseData}
        rightSlot={<span data-testid="my-slot">switch</span>}
      />,
    )
    expect(screen.getByTestId('my-slot')).toBeInTheDocument()
  })

  test('rightSlot 缺省 → __slot 容器不渲染', () => {
    const { container } = render(<ScorePercentileCard data={baseData} />)
    expect(container.querySelector('.score-percentile-card__slot')).toBeNull()
  })
})
