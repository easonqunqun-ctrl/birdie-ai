/**
 * M11-05 · 阶段通关证书 Canvas 绘制。
 */

import {
  CERT_COLORS,
  CERT_HEIGHT,
  CERT_WIDTH,
  type StageCertificateInput,
} from './certificateLayout'

export interface CertificateCanvasContext {
  fillStyle: string | CanvasGradient | CanvasPattern
  strokeStyle: string | CanvasGradient | CanvasPattern
  font: string
  textAlign: CanvasTextAlign
  textBaseline: CanvasTextBaseline
  lineWidth: number
  fillRect: (x: number, y: number, w: number, h: number) => void
  strokeRect: (x: number, y: number, w: number, h: number) => void
  beginPath: () => void
  moveTo: (x: number, y: number) => void
  lineTo: (x: number, y: number) => void
  closePath: () => void
  stroke: () => void
  fill: () => void
  fillText: (text: string, x: number, y: number, maxWidth?: number) => void
  arc: (
    x: number,
    y: number,
    r: number,
    startAngle: number,
    endAngle: number,
    counter?: boolean,
  ) => void
  save: () => void
  restore: () => void
}

export function drawStageCertificate(
  ctx: CertificateCanvasContext,
  input: StageCertificateInput,
): void {
  const { primary, primaryDark, gold, mint, white, textMuted } = CERT_COLORS

  ctx.fillStyle = primaryDark
  ctx.fillRect(0, 0, CERT_WIDTH, CERT_HEIGHT)

  ctx.fillStyle = primary
  ctx.fillRect(40, 40, CERT_WIDTH - 80, CERT_HEIGHT - 80)

  ctx.strokeStyle = gold
  ctx.lineWidth = 4
  ctx.strokeRect(56, 56, CERT_WIDTH - 112, CERT_HEIGHT - 112)

  ctx.fillStyle = white
  ctx.font = 'bold 36px sans-serif'
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.fillText('领翼 golf · 阶段通关证书', CERT_WIDTH / 2, 130)

  ctx.fillStyle = gold
  ctx.font = 'bold 72px sans-serif'
  ctx.fillText(String(input.stage), CERT_WIDTH / 2, 250)

  ctx.fillStyle = mint
  ctx.font = '28px sans-serif'
  ctx.fillText(input.stageTitle, CERT_WIDTH / 2, 310)

  ctx.fillStyle = gold
  ctx.font = 'bold 40px sans-serif'
  ctx.fillText(input.badgeLabel, CERT_WIDTH / 2, 390)

  ctx.fillStyle = white
  ctx.font = '32px sans-serif'
  ctx.fillText(`恭喜 ${input.holderName}`, CERT_WIDTH / 2, 480)

  ctx.fillStyle = textMuted
  ctx.font = '26px sans-serif'
  const courseLine =
    input.courseTitle.length > 18
      ? `${input.courseTitle.slice(0, 17)}…`
      : input.courseTitle
  ctx.fillText(`完成课程《${courseLine}》`, CERT_WIDTH / 2, 580, 560)

  ctx.fillStyle = white
  ctx.font = '24px sans-serif'
  ctx.fillText(`颁发日期：${input.issuedAtLabel}`, CERT_WIDTH / 2, 820)

  ctx.fillStyle = textMuted
  ctx.font = '22px sans-serif'
  ctx.fillText('坚持练习，下一段旅程等你开启', CERT_WIDTH / 2, 920)
}

export { CERT_WIDTH, CERT_HEIGHT }
