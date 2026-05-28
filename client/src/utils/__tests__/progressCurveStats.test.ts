import {
  computeProgressStatCards,
  findBestPhaseImprovement,
  formatDelta,
  formatProgressNarrative,
  seriesForDimension,
  shortChartDate,
  type ProgressPoint,
} from '../progressCurveStats'

const BASE_POINTS: ProgressPoint[] = [
  {
    analysis_id: 'a1',
    analyzed_at: '2026-05-01T10:00:00Z',
    overall_score: 70,
    phase_scores: { setup: 60, impact: 72 },
  },
  {
    analysis_id: 'a2',
    analyzed_at: '2026-05-10T10:00:00Z',
    overall_score: 78,
    phase_scores: { setup: 68, impact: 80 },
  },
  {
    analysis_id: 'a3',
    analyzed_at: '2026-05-20T10:00:00Z',
    overall_score: 82,
    phase_scores: { setup: 75, impact: 85 },
  },
]

describe('shortChartDate', () => {
  it('格式化为 M/D', () => {
    expect(shortChartDate('2026-05-21T08:00:00Z')).toMatch(/^\d+\/\d+$/)
  })
})

describe('seriesForDimension', () => {
  it('overall 返回全部综合分', () => {
    const s = seriesForDimension(BASE_POINTS, 'overall')
    expect(s).toHaveLength(3)
    expect(s.map((p) => p.value)).toEqual([70, 78, 82])
  })

  it('六维缺数据的点被跳过', () => {
    const pts: ProgressPoint[] = [
      { analysis_id: 'x', analyzed_at: '2026-05-01T00:00:00Z', overall_score: 80 },
      {
        analysis_id: 'y',
        analyzed_at: '2026-05-02T00:00:00Z',
        overall_score: 85,
        phase_scores: { setup: 90 },
      },
    ]
    expect(seriesForDimension(pts, 'setup')).toHaveLength(1)
    expect(seriesForDimension(pts, 'setup')[0].value).toBe(90)
  })

  // P2-W12-1：V2 报告才上 tier；V1 / 缺字段不上 tier（避免曲线点变色误导用户）
  it('V2 报告按 analysis_confidence 上 tier；V1 / 缺字段 tier=undefined', () => {
    const pts: ProgressPoint[] = [
      {
        analysis_id: 'v2_high',
        analyzed_at: '2026-05-01T00:00:00Z',
        overall_score: 80,
        engine_version: 'v2',
        analysis_confidence: 0.9, // → high
      },
      {
        analysis_id: 'v2_medium',
        analyzed_at: '2026-05-02T00:00:00Z',
        overall_score: 78,
        engine_version: 'v2',
        analysis_confidence: 0.6, // → medium
      },
      {
        analysis_id: 'v2_low',
        analyzed_at: '2026-05-03T00:00:00Z',
        overall_score: 75,
        engine_version: 'v2',
        analysis_confidence: 0.3, // → low
      },
      {
        analysis_id: 'v1_legacy',
        analyzed_at: '2026-05-04T00:00:00Z',
        overall_score: 70,
        // V1 老报告 → tier=undefined
      },
      {
        analysis_id: 'v2_no_conf',
        analyzed_at: '2026-05-05T00:00:00Z',
        overall_score: 72,
        engine_version: 'v2',
        analysis_confidence: null, // V2 但 confidence 缺 → tier=undefined
      },
    ]
    const s = seriesForDimension(pts, 'overall')
    expect(s.map((p) => p.tier)).toEqual([
      'high',
      'medium',
      'low',
      undefined,
      undefined,
    ])
  })
})

describe('findBestPhaseImprovement', () => {
  it('返回提升最大的维度', () => {
    const best = findBestPhaseImprovement(BASE_POINTS)
    expect(best).not.toBeNull()
    expect(best!.phase).toBe('setup')
    expect(best!.delta).toBe(15)
  })

  it('无正向改善时返回 null', () => {
    const pts: ProgressPoint[] = [
      {
        analysis_id: 'a',
        analyzed_at: '2026-05-01T00:00:00Z',
        overall_score: 80,
        phase_scores: { setup: 90 },
      },
      {
        analysis_id: 'b',
        analyzed_at: '2026-05-02T00:00:00Z',
        overall_score: 85,
        phase_scores: { setup: 88 },
      },
    ]
    expect(findBestPhaseImprovement(pts)).toBeNull()
  })
})

describe('computeProgressStatCards', () => {
  it('合并 user.stats 与窗口 delta', () => {
    const cards = computeProgressStatCards(BASE_POINTS, {
      total_analyses: 10,
      total_practices: 25,
      streak_days: 5,
    })
    expect(cards.totalAnalyses).toBe(10)
    expect(cards.totalPractices).toBe(25)
    expect(cards.streakDays).toBe(5)
    expect(cards.windowScoreDelta).toBe(12)
    expect(cards.bestImprovement?.phase).toBe('setup')
  })

  it('单点无 windowScoreDelta', () => {
    const cards = computeProgressStatCards([BASE_POINTS[0]], null)
    expect(cards.windowScoreDelta).toBeNull()
  })
})

describe('formatDelta', () => {
  it.each([
    [5, '+5'],
    [0, '0'],
    [-3, '-3'],
    [null, '—'],
  ])('formatDelta(%s) → %s', (input, expected) => {
    expect(formatDelta(input as number | null)).toBe(expected)
  })
})

describe('formatProgressNarrative', () => {
  it('优先输出最佳维度改善', () => {
    const cards = computeProgressStatCards(BASE_POINTS, null)
    expect(formatProgressNarrative(cards, BASE_POINTS)).toBe(
      '近 3 次分析中，站位提升 +15 分',
    )
  })

  it('单点或无改善时返回 null', () => {
    const cards = computeProgressStatCards([BASE_POINTS[0]], null)
    expect(formatProgressNarrative(cards, [BASE_POINTS[0]])).toBeNull()
  })
})
