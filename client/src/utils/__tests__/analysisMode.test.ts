import {
  defaultClubTypeForMode,
  isModeClubCompatible,
  modeClubMismatchHint,
} from '@/utils/analysisMode'

describe('analysisMode', () => {
  test('defaultClubTypeForMode', () => {
    expect(defaultClubTypeForMode('putting')).toBe('putter')
    expect(defaultClubTypeForMode('chipping')).toBe('wedge')
    expect(defaultClubTypeForMode('full_swing')).toBe('iron_7')
  })

  test('putting requires putter', () => {
    expect(isModeClubCompatible('putting', 'putter')).toBe(true)
    expect(isModeClubCompatible('putting', 'driver')).toBe(false)
    expect(modeClubMismatchHint('putting', 'driver')).toMatch(/推杆/)
  })

  test('chipping accepts wedge and short irons', () => {
    expect(isModeClubCompatible('chipping', 'wedge')).toBe(true)
    expect(isModeClubCompatible('chipping', 'iron_8')).toBe(true)
    expect(isModeClubCompatible('chipping', 'driver')).toBe(false)
  })

  test('full_swing rejects putter', () => {
    expect(isModeClubCompatible('full_swing', 'iron_7')).toBe(true)
    expect(isModeClubCompatible('full_swing', 'putter')).toBe(false)
    expect(modeClubMismatchHint('full_swing', 'putter')).toMatch(/全挥杆/)
  })

  test('compatible pairs return null hint', () => {
    expect(modeClubMismatchHint('putting', 'putter')).toBeNull()
    expect(modeClubMismatchHint('chipping', 'wedge')).toBeNull()
  })
})
