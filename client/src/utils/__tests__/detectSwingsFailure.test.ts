import { RequestError } from '@/services/request'
import {
  detectPrepareFailureBannerLines,
  normalizeDetectSwingsErrorCode,
  resolveDetectSwingsFailure,
  shouldBlockSubmitOnDetectPrepareFailure,
  type DetectSwingsFailureInfo,
} from '@/utils/detectSwingsFailure'

describe('normalizeDetectSwingsErrorCode', () => {
  test('50101 + 时长文案 → 50106', () => {
    expect(normalizeDetectSwingsErrorCode(50101, '视频时长 1.7s 不足 2.0s')).toBe(50106)
  })

  test('50101 非时长 → 保持 50101', () => {
    expect(normalizeDetectSwingsErrorCode(50101, '视频下载失败')).toBe(50101)
  })
})

describe('resolveDetectSwingsFailure', () => {
  test('50101 时长 → 视频时长过短标题', () => {
    const r = resolveDetectSwingsFailure(
      new RequestError('business', '视频时长 1.7s 不足 2.0s', { code: 50101 }),
    )
    expect(r.code).toBe(50106)
    expect(r.title).toBe('视频时长过短')
    expect(r.reshootRecommended).toBe(true)
  })

  test('50105 → 不阻断提交', () => {
    const r = resolveDetectSwingsFailure(
      new RequestError('business', '引擎不可用', { code: 50105 }),
    )
    expect(r.reshootRecommended).toBe(false)
    expect(shouldBlockSubmitOnDetectPrepareFailure(r)).toBe(false)
  })
})

describe('shouldBlockSubmitOnDetectPrepareFailure', () => {
  test('50106 → block', () => {
    const r = resolveDetectSwingsFailure(
      new RequestError('business', '视频时长 1.7s 不足 2.0s', { code: 50101 }),
    )
    expect(shouldBlockSubmitOnDetectPrepareFailure(r)).toBe(true)
  })
})

describe('detectPrepareFailureBannerLines', () => {
  test('包含 message 与 hint', () => {
    const r = resolveDetectSwingsFailure(
      new RequestError('business', '视频时长 1.7s 不足 2.0s', { code: 50101 }),
    )
    const lines = detectPrepareFailureBannerLines(r)
    expect(lines[0]).toContain('1.7')
    expect(lines.some((l) => /2 秒|2秒/.test(l))).toBe(true)
  })
})
