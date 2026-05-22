import { linesForQualityBlocks } from '@/constants/qualityBlockers'

describe('linesForQualityBlocks', () => {
  test('空/null → []', () => {
    expect(linesForQualityBlocks(null)).toEqual([])
    expect(linesForQualityBlocks([])).toEqual([])
  })

  test('已知 code → 固定文案', () => {
    expect(linesForQualityBlocks(['too_dark'])).toEqual([
      expect.stringMatching(/过暗/),
    ])
    expect(linesForQualityBlocks(['too_blurry'])).toEqual([
      expect.stringMatching(/模糊/),
    ])
    expect(linesForQualityBlocks(['too_shaky'])).toEqual([
      expect.stringMatching(/抖动/),
    ])
  })

  test('未知 code → 兜底模板', () => {
    const lines = linesForQualityBlocks(['custom_block'])
    expect(lines[0]).toContain('custom_block')
  })

  test('空字符串 code 被跳过', () => {
    expect(linesForQualityBlocks(['too_dark', '', '  '])).toHaveLength(1)
  })
})
