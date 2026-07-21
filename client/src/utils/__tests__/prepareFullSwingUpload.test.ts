import {
  canReusePreparedUpload,
  isPrepareInFlight,
  prepareBackgroundStatusHint,
  shouldBlockSubmitWhilePreparing,
  shouldShowPrepareSlowPathHint,
  shouldSkipDetectWaitOnSubmit,
  shouldStartPrepareFullSwingUpload,
} from '../prepareFullSwingUpload'

describe('shouldStartPrepareFullSwingUpload', () => {
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
})

describe('submit while preparing (A: non-blocking)', () => {
  test('never blocks submit during upload or detect', () => {
    expect(shouldBlockSubmitWhilePreparing('uploading')).toBe(false)
    expect(shouldBlockSubmitWhilePreparing('detecting')).toBe(false)
    expect(shouldBlockSubmitWhilePreparing('ready')).toBe(false)
  })

  test('reuse only when ready', () => {
    expect(canReusePreparedUpload('ready')).toBe(true)
    expect(canReusePreparedUpload('failed')).toBe(false)
    expect(canReusePreparedUpload('uploading')).toBe(false)
  })
})

describe('prepare background hints (B)', () => {
  test('isPrepareInFlight covers uploading and detecting', () => {
    expect(isPrepareInFlight('uploading')).toBe(true)
    expect(isPrepareInFlight('detecting')).toBe(true)
    expect(isPrepareInFlight('ready')).toBe(false)
  })

  test('slow path hint only after unlock', () => {
    expect(shouldShowPrepareSlowPathHint('uploading', false)).toBe(false)
    expect(shouldShowPrepareSlowPathHint('uploading', true)).toBe(true)
    expect(shouldShowPrepareSlowPathHint('ready', true)).toBe(false)
  })

  test('upload phase copy includes progress when available', () => {
    expect(prepareBackgroundStatusHint('uploading', 42, false)).toBe(
      '正在后台上传视频 42%…',
    )
    expect(prepareBackgroundStatusHint('uploading', 0, false)).toBe(
      '正在后台上传视频…',
    )
    expect(prepareBackgroundStatusHint('uploading', 10, true)).toContain(
      '开始分析',
    )
  })

  test('detect phase copy nudges manual angle after timeout', () => {
    expect(prepareBackgroundStatusHint('detecting', null, false)).toBe(
      '正在识别拍摄机位… 可先选球杆。',
    )
    expect(prepareBackgroundStatusHint('detecting', null, true)).toContain(
      '手动选择机位',
    )
  })

  test('idle phases return null hint', () => {
    expect(prepareBackgroundStatusHint('ready', null, false)).toBeNull()
    expect(prepareBackgroundStatusHint('idle', null, false)).toBeNull()
  })
})

describe('shouldSkipDetectWaitOnSubmit', () => {
  test('only when detecting with upload token ready', () => {
    expect(shouldSkipDetectWaitOnSubmit('detecting', true)).toBe(true)
    expect(shouldSkipDetectWaitOnSubmit('detecting', false)).toBe(false)
    expect(shouldSkipDetectWaitOnSubmit('uploading', true)).toBe(false)
    expect(shouldSkipDetectWaitOnSubmit('ready', true)).toBe(false)
  })
})
