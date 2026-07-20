import {
  extractVideoExt,
  formatVideoPickSummary,
  normalizeLocalVideoUri,
  normalizePickerDurationSeconds,
  validatePickedVideo,
} from '@/utils/videoPickNormalize'

describe('normalizePickerDurationSeconds', () => {
  test('秒原样', () => {
    expect(normalizePickerDurationSeconds(5.2)).toBe(5.2)
  })
  test('毫秒转秒', () => {
    expect(normalizePickerDurationSeconds(5200)).toBe(5.2)
  })
  test('非法 → 0', () => {
    expect(normalizePickerDurationSeconds(NaN)).toBe(0)
    expect(normalizePickerDurationSeconds(-1)).toBe(0)
  })
})

describe('extractVideoExt / normalizeLocalVideoUri', () => {
  test('扩展名忽略 query', () => {
    expect(extractVideoExt('file:///tmp/a.MOV?x=1')).toBe('mov')
  })
  test('无扩展名', () => {
    expect(extractVideoExt('content://media/123')).toBe('')
  })
  test('绝对路径补 file://', () => {
    expect(normalizeLocalVideoUri('/var/mobile/Containers/Data/a.mp4')).toBe(
      'file:///var/mobile/Containers/Data/a.mp4',
    )
  })
  test('已有 scheme 不改', () => {
    expect(normalizeLocalVideoUri('content://foo')).toBe('content://foo')
    expect(normalizeLocalVideoUri('file:///tmp/a.mp4')).toBe('file:///tmp/a.mp4')
  })
})

describe('validatePickedVideo', () => {
  test('时长过短', () => {
    expect(
      validatePickedVideo({ filePath: 'a.mp4', size: 1000, duration: 0.5 }),
    ).toMatch(/短|秒/)
  })
  test('无扩展名放行', () => {
    expect(
      validatePickedVideo({
        filePath: 'content://media/video/12',
        size: 1024,
        duration: 4,
      }),
    ).toBeNull()
  })
  test('不支持扩展名', () => {
    expect(
      validatePickedVideo({ filePath: 'a.avi', size: 1024, duration: 4 }),
    ).toMatch(/avi/)
  })
})

describe('formatVideoPickSummary', () => {
  test('拼出可粘贴摘要', () => {
    const s = formatVideoPickSummary({
      source: 'album',
      preset: 'high_quality',
      width: 1920,
      height: 1080,
      duration: 6.5,
      size: 12 * 1024 * 1024,
      filePath: 'file:///tmp/x.mov',
    })
    expect(s).toContain('source=album')
    expect(s).toContain('1920×1080')
    expect(s).toContain('6.50s')
    expect(s).toContain('mov')
  })
})
