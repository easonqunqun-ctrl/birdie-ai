/**
 * `posterCanvas.drawPoster` 单测（Q-C1）。
 *
 * Canvas 在 jsdom 里没有真实渲染，但 ctx 的"调用顺序 + 参数"完全可断言。
 * 我们用一个轻量 mock 记录所有 setter / 调用，验证：
 *   1. 大字号的"综合分数"被绘制
 *   2. 评级徽章文案出现
 *   3. 至少绘出 5 圈背景多边形（雷达图骨架）
 *   4. 问题列表条数与输入一致
 *   5. 缺分 / 缺 level 时优雅兜底（"--" / "待评级"）
 */

import { drawPoster, formatScore, POSTER_LEVEL_LABEL, type PosterCanvasContext } from '../posterCanvas'
import { POSTER_BOTTOM, POSTER_WIDTH, POSTER_WXA_CODE_SRC_SIZE, posterCtaBottomY, posterIssuesBottomY, type PosterInput } from '../posterLayout'

type Call = { method: string; args: unknown[] }

function createMockCtx(): PosterCanvasContext & { calls: Call[] } {
  const calls: Call[] = []
  const push = (method: string, ...args: unknown[]) => calls.push({ method, args })
  const ctx: PosterCanvasContext & { calls: Call[] } = {
    calls,
    fillStyle: '',
    strokeStyle: '',
    font: '',
    textAlign: 'start',
    textBaseline: 'alphabetic',
    lineWidth: 1,
    globalAlpha: 1,
    fillRect: (...a) => push('fillRect', ...a),
    strokeRect: (...a) => push('strokeRect', ...a),
    beginPath: () => push('beginPath'),
    moveTo: (...a) => push('moveTo', ...a),
    lineTo: (...a) => push('lineTo', ...a),
    closePath: () => push('closePath'),
    stroke: () => push('stroke'),
    fill: () => push('fill'),
    fillText: (...a) => push('fillText', ...a),
    arc: (...a) => push('arc', ...a),
    drawImage: (...a) => push('drawImage', ...a),
    save: () => push('save'),
    restore: () => push('restore'),
  }
  return ctx
}

function fillTexts(calls: Call[]): string[] {
  return calls.filter((c) => c.method === 'fillText').map((c) => c.args[0] as string)
}

const baseInput: PosterInput = {
  overallScore: 86,
  scoreLevel: 'great',
  phaseScores: [80, 85, 82, 90, 78, 88],
  phaseLabels: ['站位', '上杆', '顶点', '下杆', '击球', '收杆'],
  clubLabel: '7 号铁',
  thumbnailUrl: null,
  wxaCodeUrl: 'https://cdn.example/wxa.png',
  topIssues: ['头部抬起过早', '左肘弯曲', '收杆失衡'],
  cameraAngleLabel: '正面',
}

describe('drawPoster · 正常场景', () => {
  it('返回正确 accentColor / scoreText / levelText / issuesDrawn', () => {
    const ctx = createMockCtx()
    const res = drawPoster(ctx, baseInput)
    expect(res.accentColor).toBe('#1a237e')
    expect(res.scoreText).toBe('86')
    expect(res.levelText).toBe('进阶球员')
    expect(res.issuesDrawn).toBe(3)
  })

  it('海报顶部出现 LOGO + 评级徽章', () => {
    const ctx = createMockCtx()
    drawPoster(ctx, baseInput)
    const texts = fillTexts(ctx.calls)
    expect(texts).toEqual(expect.arrayContaining(['领翼golf', POSTER_LEVEL_LABEL.great]))
  })

  it('分数 + 球杆 + 主要问题全部入画', () => {
    const ctx = createMockCtx()
    drawPoster(ctx, baseInput)
    const texts = fillTexts(ctx.calls)
    expect(texts).toContain('86')
    expect(texts).toEqual(expect.arrayContaining(['头部抬起过早', '左肘弯曲', '收杆失衡']))
    expect(texts.some((t) => t.includes('7 号铁'))).toBe(true)
  })

  it('V2 报告在分数卡左下角绘制可信度标签', () => {
    const ctx = createMockCtx()
    drawPoster(ctx, {
      ...baseInput,
      engineVersion: 'v2',
      analysisConfidence: 0.806,
    })
    const texts = fillTexts(ctx.calls)
    expect(texts).toContain('AI 高可信 81%')
  })

  it('V1 报告不在海报上绘制可信度标签', () => {
    const ctx = createMockCtx()
    drawPoster(ctx, {
      ...baseInput,
      engineVersion: 'v1',
      analysisConfidence: 1.0,
    })
    const texts = fillTexts(ctx.calls)
    expect(texts.some((t) => t.startsWith('AI 高可信'))).toBe(false)
  })

  it('雷达图绘制至少 5 圈背景（每圈一次 beginPath/closePath/stroke）', () => {
    const ctx = createMockCtx()
    drawPoster(ctx, baseInput)
    const closeCount = ctx.calls.filter((c) => c.method === 'closePath').length
    // 5 圈背景 + 1 个数据多边形 = 至少 6
    expect(closeCount).toBeGreaterThanOrEqual(6)
  })

  it('画 6 个阶段标签', () => {
    const ctx = createMockCtx()
    drawPoster(ctx, baseInput)
    const texts = fillTexts(ctx.calls)
    for (const label of baseInput.phaseLabels) {
      expect(texts).toContain(label)
    }
  })

  it('有 wxa 图片时用整图尺寸 drawImage（避免只裁左上角导致码偏右下）', () => {
    const ctx = createMockCtx()
    const fakeImg = { fake: true, width: POSTER_WXA_CODE_SRC_SIZE, height: POSTER_WXA_CODE_SRC_SIZE }
    drawPoster(ctx, baseInput, { wxaCodeImage: fakeImg, thumbnailImage: null })
    const draw = ctx.calls.find((c) => c.method === 'drawImage')
    expect(draw).toBeDefined()
    const qrX = POSTER_WIDTH - POSTER_BOTTOM.marginX - POSTER_BOTTOM.qrSize
    expect(draw!.args).toEqual([
      fakeImg,
      0,
      0,
      POSTER_WXA_CODE_SRC_SIZE,
      POSTER_WXA_CODE_SRC_SIZE,
      qrX,
      POSTER_BOTTOM.ctaTop,
      POSTER_BOTTOM.qrSize,
      POSTER_BOTTOM.qrSize,
    ])
  })

  it('wxa 图片缺少 width/height 时回退 POSTER_WXA_CODE_SRC_SIZE', () => {
    const ctx = createMockCtx()
    const fakeImg = { fake: true }
    drawPoster(ctx, baseInput, { wxaCodeImage: fakeImg, thumbnailImage: null })
    const draw = ctx.calls.find((c) => c.method === 'drawImage')
    expect(draw).toBeDefined()
    expect(draw!.args[3]).toBe(POSTER_WXA_CODE_SRC_SIZE)
    expect(draw!.args[4]).toBe(POSTER_WXA_CODE_SRC_SIZE)
  })

  it('主要问题区、CTA 区与页脚 Y 坐标不重叠', () => {
    expect(posterIssuesBottomY(3)).toBeLessThan(POSTER_BOTTOM.ctaTop)
    expect(posterCtaBottomY()).toBeLessThan(POSTER_BOTTOM.footerY - 28)
    const ctx = createMockCtx()
    drawPoster(ctx, baseInput)
    const promoY = ctx.calls.find(
      (c) => c.method === 'fillText' && c.args[0] === '扫码看完整报告',
    )?.args[2] as number | undefined
    expect(typeof promoY).toBe('number')
    expect(promoY!).toBeGreaterThanOrEqual(POSTER_BOTTOM.ctaTop)
  })

  it('小程序码缺失时绘制占位说明而非空白灰块', () => {
    const ctx = createMockCtx()
    drawPoster(ctx, baseInput, { wxaCodeImage: null, thumbnailImage: null })
    expect(fillTexts(ctx.calls)).toEqual(expect.arrayContaining(['扫码体验']))
  })
})

describe('drawPoster · 兜底场景', () => {
  it('overallScore 为 null 时分数显示为 "--"，且不报错', () => {
    const ctx = createMockCtx()
    const res = drawPoster(ctx, { ...baseInput, overallScore: null, scoreLevel: null })
    expect(res.scoreText).toBe('--')
    expect(res.levelText).toBe('--')
    expect(fillTexts(ctx.calls)).toContain('--')
  })

  it('scoreLevel 为空但有分数 → 走 deriveLevel 推一档', () => {
    const ctx = createMockCtx()
    const res = drawPoster(ctx, { ...baseInput, scoreLevel: null, overallScore: 76 })
    expect(res.levelText).toBe('良好')
    expect(res.accentColor).toBe('#3b82f6')
  })

  it('topIssues 为空时画兜底提示，不画问号', () => {
    const ctx = createMockCtx()
    const res = drawPoster(ctx, { ...baseInput, topIssues: [] })
    expect(res.issuesDrawn).toBe(0)
    expect(fillTexts(ctx.calls)).toEqual(expect.arrayContaining(['暂未识别到突出问题，继续保持！']))
  })

  it('phaseScores 为空数组时雷达图骨架仍绘制', () => {
    const ctx = createMockCtx()
    expect(() =>
      drawPoster(ctx, { ...baseInput, phaseScores: [], phaseLabels: [] }),
    ).not.toThrow()
    const closeCount = ctx.calls.filter((c) => c.method === 'closePath').length
    expect(closeCount).toBeGreaterThanOrEqual(5)
  })

  it('wxaCodeImage 缺失时画灰底占位，依旧不报错', () => {
    const ctx = createMockCtx()
    expect(() => drawPoster(ctx, baseInput, { wxaCodeImage: null, thumbnailImage: null })).not.toThrow()
    expect(ctx.calls.some((c) => c.method === 'drawImage')).toBe(false)
  })

  it('过长的主要问题会被截断追加 …', () => {
    const ctx = createMockCtx()
    const longIssue = '这是一句非常非常非常长的问题描述应该会被截断处理掉'
    drawPoster(ctx, { ...baseInput, topIssues: [longIssue] })
    const texts = fillTexts(ctx.calls)
    const rendered = texts.find((t) => t.includes('这是一句'))
    expect(rendered).toBeDefined()
    expect(rendered!.endsWith('…')).toBe(true)
  })
})

describe('formatScore', () => {
  it.each([
    [null, '--'],
    [undefined, '--'],
    [NaN, '--'],
    [85.4, '85'],
    [85.5, '86'],
    [100, '100'],
    [0, '0'],
  ])('分数 %s → "%s"', (input, expected) => {
    expect(formatScore(input as number | null | undefined)).toBe(expected)
  })
})
