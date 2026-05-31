import {
  CLIENT_MIN_DURATION_GATE_SECONDS,
  validateVideoDurationForUpload,
} from '@/utils/videoDurationValidation'

describe('validateVideoDurationForUpload', () => {
  test('1.7s → 太短（对应线上 50101）', () => {
    const msg = validateVideoDurationForUpload(1.7)
    expect(msg).toMatch(/太短/)
    expect(msg).toMatch(/1\.7/)
  })

  test('2.0s → 仍低于客户端门禁', () => {
    expect(validateVideoDurationForUpload(2.0)).toMatch(/太短/)
  })

  test('2.3s 边界 → 通过', () => {
    expect(validateVideoDurationForUpload(CLIENT_MIN_DURATION_GATE_SECONDS)).toBeNull()
  })

  test('31s → 太长', () => {
    expect(validateVideoDurationForUpload(31)).toMatch(/太长/)
  })
})
