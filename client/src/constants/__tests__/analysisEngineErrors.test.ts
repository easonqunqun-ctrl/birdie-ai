import {
  REGISTERED_ENGINE_ERROR_CODES,
  describeAnalysisFailure,
} from '@/constants/analysisEngineErrors'

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

  // ============================================================
  // P2-M7-03：registry 完整性测试（AC-2 CI 门禁）
  // 每个 ai_engine ERROR_REGISTRY 注册的码都必须有 ENGINE_FAILURE_COPY 条目
  // ============================================================
  test.each(REGISTERED_ENGINE_ERROR_CODES)(
    'registered code %i 必须有 ENGINE_FAILURE_COPY 条目（AC-2）',
    (code) => {
      const r = describeAnalysisFailure({ code, message: '' })
      // 不能落 GENERIC_FAILURE 兜底
      expect(r.title).not.toBe('分析失败')
      expect(r.hint).toBeTruthy()
      expect(typeof r.reshootRecommended).toBe('boolean')
    },
  )

  test('REGISTERED_ENGINE_ERROR_CODES 覆盖 50101-50123 全段（M7-03 §3.3）', () => {
    expect(REGISTERED_ENGINE_ERROR_CODES).toHaveLength(23)
    expect(REGISTERED_ENGINE_ERROR_CODES).toEqual(
      expect.arrayContaining([
        50101, 50102, 50103, 50104, 50105,
        50106, 50107, 50108, 50109, 50110,
        50111, 50112, 50113, 50114, 50115,
        50116, 50117, 50118, 50119, 50120,
        50121, 50122, 50123,
      ]),
    )
  })

  test('50106 视频过短 → title 命中', () => {
    const r = describeAnalysisFailure({ code: 50106, message: 'duration < 3s' })
    expect(r.title).toBe('视频时长过短')
    expect(r.hint).toMatch(/3 秒/)
  })

  test('50109 暗光 → AC-3 真机场景命中', () => {
    const r = describeAnalysisFailure({ code: 50109, message: '光线不足' })
    expect(r.title).toBe('光线不足')
    expect(r.hint).toMatch(/光线/)
  })

  test('50110 抖动 → AC-3 真机场景命中', () => {
    const r = describeAnalysisFailure({ code: 50110, message: '抖动' })
    expect(r.title).toBe('画面抖动过大')
    expect(r.hint).toMatch(/三脚架|手持/)
  })

  test('50113 半身 → AC-3 真机场景命中', () => {
    const r = describeAnalysisFailure({ code: 50113, message: '半身' })
    expect(r.title).toBe('人物未完整入镜')
    expect(r.hint).toMatch(/完整|退后/)
  })

  test('50120 codec → M7-02 联动', () => {
    const r = describeAnalysisFailure({ code: 50120, message: 'HEVC' })
    expect(r.title).toBe('视频格式暂不支持')
    expect(r.hint).toMatch(/H\.264|兼容性|mp4/i)
  })

  test('50118/50119 系统类 → reshootRecommended=false', () => {
    expect(describeAnalysisFailure({ code: 50118, message: '' }).reshootRecommended).toBe(false)
    expect(describeAnalysisFailure({ code: 50119, message: '' }).reshootRecommended).toBe(false)
  })

  test('文案 NFR title ≤ 30 字 / hint ≤ 80 字（M7-03 §3.1）', () => {
    for (const code of REGISTERED_ENGINE_ERROR_CODES) {
      const r = describeAnalysisFailure({ code, message: '' })
      expect(r.title.length).toBeLessThanOrEqual(30)
      if (r.hint) {
        expect(r.hint.length).toBeLessThanOrEqual(80)
      }
    }
  })
})
