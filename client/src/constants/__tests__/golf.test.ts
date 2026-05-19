import {
  FREQ_LABEL,
  FREQS,
  GOAL_LABEL,
  GOALS,
  LEVEL_LABEL,
  LEVELS,
  MAX_GOALS,
} from '@/constants/golf'

describe('golf constants', () => {
  test('LEVEL_LABEL 覆盖所有 LEVELS', () => {
    for (const l of LEVELS) {
      expect(LEVEL_LABEL[l.value]).toBe(l.label)
    }
  })

  test('GOAL_LABEL / FREQ_LABEL 与选项表一致', () => {
    for (const g of GOALS) {
      expect(GOAL_LABEL[g.value]).toBe(g.label)
    }
    for (const f of FREQS) {
      expect(FREQ_LABEL[f.value]).toBe(f.label)
    }
  })

  test('MAX_GOALS = 3', () => {
    expect(MAX_GOALS).toBe(3)
  })
})
