import {
  aggregatePracticeCounts,
  buildPracticeCalendarGrid,
  parseMonthKey,
  shiftMonthKey,
} from '../practiceCalendarLayout'

describe('practiceCalendarLayout', () => {
  it('parseMonthKey 合法', () => {
    expect(parseMonthKey('2026-05')).toEqual({ year: 2026, month: 5 })
  })

  it('shiftMonthKey 跨年', () => {
    expect(shiftMonthKey('2026-01', -1)).toBe('2025-12')
    expect(shiftMonthKey('2026-12', 1)).toBe('2027-01')
  })

  it('aggregatePracticeCounts 按日聚合', () => {
    const m = aggregatePracticeCounts([
      { practice_date: '2026-05-10' },
      { practice_date: '2026-05-10' },
      { practice_date: '2026-05-11' },
    ])
    expect(m.get('2026-05-10')).toBe(2)
    expect(m.get('2026-05-11')).toBe(1)
  })

  it('buildPracticeCalendarGrid 含 6 行与 monthTotal', () => {
    const counts = aggregatePracticeCounts([{ practice_date: '2026-05-03' }])
    const grid = buildPracticeCalendarGrid('2026-05', counts, '2026-05-03')
    expect(grid.weeks).toHaveLength(6)
    expect(grid.weeks[0]).toHaveLength(7)
    expect(grid.monthTotal).toBe(1)
    const hit = grid.weeks.flat().find((c) => c.dateKey === '2026-05-03')
    expect(hit?.count).toBe(1)
    expect(hit?.isToday).toBe(true)
  })
})
