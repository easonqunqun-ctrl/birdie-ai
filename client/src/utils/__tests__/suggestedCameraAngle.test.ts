import {
  applyDetectedCameraAngle,
  resolveSuggestedCameraAngle,
  suggestedCameraAngleHintCopy,
  suggestedCameraAngleToastCopy,
} from '../suggestedCameraAngle'
import {
  canReusePreparedUpload,
  shouldBlockSubmitWhilePreparing,
  shouldStartPrepareFullSwingUpload,
} from '../prepareFullSwingUpload'

describe('applyDetectedCameraAngle', () => {
  test('applies suggestion when user has not touched', () => {
    const r = applyDetectedCameraAngle('face_on', { suggested_camera_angle: 'down_the_line' }, false)
    expect(r.angle).toBe('down_the_line')
    expect(r.autoApplied).toBe(true)
    expect(r.hint).toBe(suggestedCameraAngleHintCopy('down_the_line'))
  })

  test('keeps user choice when touched', () => {
    const r = applyDetectedCameraAngle('face_on', { suggested_camera_angle: 'down_the_line' }, true)
    expect(r).toEqual({ angle: 'face_on', autoApplied: false, hint: null })
  })

  test('null suggestion leaves default', () => {
    const r = applyDetectedCameraAngle('face_on', { suggested_camera_angle: null }, false)
    expect(r).toEqual({ angle: 'face_on', autoApplied: false, hint: null })
  })
})

describe('prepareFullSwingUpload guards', () => {
  test('starts only for valid full_swing after quality', () => {
    expect(
      shouldStartPrepareFullSwingUpload({
        tempFilePath: '/tmp/a.mp4',
        size: 1000,
        duration: 5,
        analysisMode: 'full_swing',
        qualityChecking: false,
        qualityBlockCount: 0,
      }),
    ).toBe(true)
    expect(
      shouldStartPrepareFullSwingUpload({
        tempFilePath: '/tmp/a.mp4',
        size: 1000,
        duration: 5,
        analysisMode: 'putting',
        qualityChecking: false,
        qualityBlockCount: 0,
      }),
    ).toBe(false)
  })

  test('submit blocked while uploading or detecting', () => {
    expect(shouldBlockSubmitWhilePreparing('uploading')).toBe(true)
    expect(shouldBlockSubmitWhilePreparing('detecting')).toBe(true)
    expect(shouldBlockSubmitWhilePreparing('ready')).toBe(false)
  })

  test('reuse only when ready', () => {
    expect(canReusePreparedUpload('ready')).toBe(true)
    expect(canReusePreparedUpload('failed')).toBe(false)
  })
})

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
