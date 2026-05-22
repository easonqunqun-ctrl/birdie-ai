import { describeAnalysisFailure } from '@/constants/analysisEngineErrors'

describe('describeAnalysisFailure', () => {
  test('null/undefined → 通用失败文案', () => {
    expect(describeAnalysisFailure(null)).toMatchObject({
      title: '分析失败',
      reshootRecommended: true,
    })
    expect(describeAnalysisFailure(undefined).message).toContain('没能完成')
  })

  test('50100 → 连接失败，不优先重拍', () => {
    expect(describeAnalysisFailure({ code: 50100, message: '引擎超时' })).toEqual({
      title: '分析服务连接失败',
      message: '引擎超时',
      hint: expect.stringMatching(/稍后再试/),
      reshootRecommended: false,
    })
  })

  test('50102 → 画质阻断，优先重拍', () => {
    const r = describeAnalysisFailure({
      code: 50102,
      message: '视频画质不足，建议在光线充足的环境下重拍',
    })
    expect(r.title).toBe('视频画质未达标')
    expect(r.reshootRecommended).toBe(true)
    expect(r.hint).toMatch(/光线/)
  })

  test('50103 → 未检测到人体', () => {
    const r = describeAnalysisFailure({ code: 50103, message: '未检测到挥杆' })
    expect(r.title).toBe('未检测到挥杆人物')
    expect(r.hint).toMatch(/全身/)
  })

  test('50104 → 未检测到挥杆动作', () => {
    const r = describeAnalysisFailure({ code: 50104, message: '' })
    expect(r.title).toBe('未识别到完整挥杆')
    expect(r.message).toBe('未识别到完整挥杆')
  })

  test('50105 → 引擎内部异常', () => {
    expect(
      describeAnalysisFailure({ code: 50105, message: 'AI 引擎内部异常' }).reshootRecommended,
    ).toBe(false)
  })

  test('未知码 → 兜底 + 保留后端 message', () => {
    expect(
      describeAnalysisFailure({ code: 50999, message: '自定义错误' }).message,
    ).toBe('自定义错误')
  })
})
