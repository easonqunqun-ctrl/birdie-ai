import { linesForQualityWarnings } from '@/constants/qualityWarnings'

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
  })

  test('未知 code → 兜底模板', () => {
    const lines = linesForQualityWarnings(['custom_code'])
    expect(lines[0]).toContain('custom_code')
  })

  test('空字符串 code 被跳过', () => {
    expect(linesForQualityWarnings(['low_light', '', '  '])).toHaveLength(1)
  })
})
