import { formatPgcTimeMarker } from '@/utils/pgcTimeMarker'

describe('formatPgcTimeMarker', () => {
  test('null → 全程', () => {
    expect(formatPgcTimeMarker(null)).toBe('全程')
  })

  test('formats mm:ss', () => {
    expect(formatPgcTimeMarker(65000)).toBe('1:05')
    expect(formatPgcTimeMarker(2200)).toBe('0:02')
  })
})
