import { SCORE_LEVEL_META, scoreLevelFromScore } from '@/constants/scoreLevel'

describe('scoreLevelFromScore', () => {
  test('null/undefined → null', () => {
    expect(scoreLevelFromScore(null)).toBeNull()
    expect(scoreLevelFromScore(undefined)).toBeNull()
  })

  test('边界分档与 backend score_level 对齐', () => {
    expect(scoreLevelFromScore(90)).toBe('excellent')
    expect(scoreLevelFromScore(89)).toBe('great')
    expect(scoreLevelFromScore(80)).toBe('great')
    expect(scoreLevelFromScore(79)).toBe('good')
    expect(scoreLevelFromScore(70)).toBe('good')
    expect(scoreLevelFromScore(69)).toBe('fair')
    expect(scoreLevelFromScore(60)).toBe('fair')
    expect(scoreLevelFromScore(59)).toBe('needs_improvement')
  })
})

describe('SCORE_LEVEL_META', () => {
  test('五档均有 label 与 cssVar', () => {
    for (const key of [
      'excellent',
      'great',
      'good',
      'fair',
      'needs_improvement',
    ] as const) {
      expect(SCORE_LEVEL_META[key].label.length).toBeGreaterThan(0)
      expect(SCORE_LEVEL_META[key].cssVar).toMatch(/var\(--|#/)
    }
  })
})
