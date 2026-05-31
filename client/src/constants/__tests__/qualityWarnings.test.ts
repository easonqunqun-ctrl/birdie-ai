import {
  linesForQualityWarnings,
  QUALITY_WARNING_IMPACT_FOOTNOTE,
} from '@/constants/qualityWarnings'

describe('linesForQualityWarnings', () => {
  test('空/null → []', () => {
    expect(linesForQualityWarnings(null)).toEqual([])
    expect(linesForQualityWarnings([])).toEqual([])
  })

  test('已知 code → 固定文案', () => {
    expect(linesForQualityWarnings(['low_light'])).toEqual([
      expect.stringMatching(/光线偏暗/),
    ])
    expect(linesForQualityWarnings(['camera_shake'])).toEqual([
      expect.stringMatching(/抖动/),
    ])
    expect(linesForQualityWarnings(['partial_occlusion'])).toEqual([
      expect.stringMatching(/遮挡/),
    ])
    expect(linesForQualityWarnings(['low_pose_confidence'])).toEqual([
      expect.stringMatching(/置信度/),
    ])
    expect(linesForQualityWarnings(['rotation_reading_unreliable'])).toEqual([
      expect.stringMatching(/无法稳定读取转肩角度/),
    ])
    expect(linesForQualityWarnings(['top_frame_mismatch'])).toEqual([
      expect.stringMatching(/顶点时刻与转肩峰值/),
    ])
  })

  test('未知 code → 兜底模板', () => {
    const lines = linesForQualityWarnings(['custom_code'])
    expect(lines[0]).toContain('custom_code')
  })

  test('空字符串 code 被跳过', () => {
    expect(linesForQualityWarnings(['low_light', '', '  '])).toHaveLength(1)
  })

  test('QUALITY_WARNING_IMPACT_FOOTNOTE 非空', () => {
    expect(QUALITY_WARNING_IMPACT_FOOTNOTE).toMatch(/结果可能受影响/)
  })
})
