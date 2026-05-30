/**
 * `drawPosterTimeline` 单测（W19-A）。
 */

import { drawPosterTimeline } from '../posterCanvasTimeline'
import { POSTER_TL_TAGLINE, POSTER_TL_CTA_TEXT } from '../posterTimelineLayout'
import type { PosterCanvasContext } from '../posterCanvas'
import type { PosterInput } from '../posterLayout'

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
  overallScore: 88,
  scoreLevel: 'great',
  phaseScores: [80, 85, 82, 90, 78, 88],
  phaseLabels: ['站位', '上杆', '顶点', '下杆', '击球', '收杆'],
  clubLabel: '7 号铁',
  cameraAngleLabel: '正面',
  thumbnailUrl: null,
  wxaCodeUrl: null,
  topIssues: ['头部抬起过早', '左肘弯曲'],
}

describe('drawPosterTimeline', () => {
  it('绘制朋友圈标语 + 分数 + CTA', () => {
    const ctx = createMockCtx()
    const res = drawPosterTimeline(ctx, baseInput)
    const texts = fillTexts(ctx.calls)
    expect(texts).toEqual(expect.arrayContaining([POSTER_TL_TAGLINE, '88', POSTER_TL_CTA_TEXT]))
    expect(res.scoreText).toBe('88')
    expect(res.issuesDrawn).toBe(2)
  })

  it('缺分时兜底 --', () => {
    const ctx = createMockCtx()
    const res = drawPosterTimeline(ctx, { ...baseInput, overallScore: null, scoreLevel: null })
    expect(res.scoreText).toBe('--')
    expect(fillTexts(ctx.calls)).toContain('--')
  })
})
