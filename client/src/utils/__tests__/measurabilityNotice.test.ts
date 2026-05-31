import { linesForMeasurabilityNotice } from '../measurabilityNotice'

describe('linesForMeasurabilityNotice', () => {
  test('dtl explains skipped rotation dimensions', () => {
    const lines = linesForMeasurabilityNotice('down_the_line', [])
    expect(lines.some((l) => l.includes('旋转'))).toBe(true)
  })

  test('face_on without dtl notice stays empty', () => {
    expect(linesForMeasurabilityNotice('face_on', ['rotation_reading_unreliable'])).toEqual([])
  })
})
