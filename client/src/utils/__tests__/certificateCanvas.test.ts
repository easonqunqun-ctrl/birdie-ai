import { drawStageCertificate } from '@/utils/certificateCanvas'

describe('certificateCanvas', () => {
  test('drawStageCertificate invokes canvas primitives', () => {
    const calls: string[] = []
    const ctx = {
      fillStyle: '',
      strokeStyle: '',
      font: '',
      textAlign: 'center' as CanvasTextAlign,
      textBaseline: 'middle' as CanvasTextBaseline,
      lineWidth: 1,
      fillRect: () => calls.push('fillRect'),
      strokeRect: () => calls.push('strokeRect'),
      beginPath: () => calls.push('beginPath'),
      moveTo: () => undefined,
      lineTo: () => undefined,
      closePath: () => undefined,
      stroke: () => calls.push('stroke'),
      fill: () => calls.push('fill'),
      fillText: () => calls.push('fillText'),
      arc: () => undefined,
      save: () => undefined,
      restore: () => undefined,
    }
    drawStageCertificate(ctx, {
      holderName: '测试',
      courseTitle: '基础挥杆',
      stage: 1,
      stageTitle: '第 1 阶 · 入门',
      badgeLabel: '入门过关',
      issuedAtLabel: '2026年05月29日',
    })
    expect(calls).toContain('strokeRect')
    expect(calls.filter((c) => c === 'fillText').length).toBeGreaterThan(3)
  })
})
