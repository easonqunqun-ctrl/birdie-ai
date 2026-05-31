import {
  resolveSuggestedCameraAngle,
  suggestedCameraAngleToastCopy,
} from '../suggestedCameraAngle'

describe('resolveSuggestedCameraAngle', () => {
  test('applies high-confidence suggestion', () => {
    expect(
      resolveSuggestedCameraAngle('face_on', { suggested_camera_angle: 'down_the_line' }),
    ).toEqual({ angle: 'down_the_line', changed: true })
  })

  test('keeps current when suggestion null', () => {
    expect(
      resolveSuggestedCameraAngle('face_on', { suggested_camera_angle: null }),
    ).toEqual({ angle: 'face_on', changed: false })
  })

  test('unchanged when suggestion matches current', () => {
    expect(
      resolveSuggestedCameraAngle('face_on', { suggested_camera_angle: 'face_on' }),
    ).toEqual({ angle: 'face_on', changed: false })
  })
})

describe('suggestedCameraAngleToastCopy', () => {
  test('uses localized angle label', () => {
    expect(suggestedCameraAngleToastCopy('down_the_line')).toContain('侧面')
  })
})
