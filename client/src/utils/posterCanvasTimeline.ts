/**
 * 朋友圈封面海报 Canvas 2D 绘制（W19-A / Q-B2）。
 *
 * 1080×1920 三段式版式，锚点见 `posterTimelineLayout.ts`。
 * 与 750×1334 `drawPoster` 共用色板 / 几何 / 输入类型。
 */

import type { AnalysisScoreLevel } from '@/types/analysis'
import {
  POSTER_COLORS,
  POSTER_WXA_CODE_SRC_SIZE,
  PosterInput,
  axisLabelAnchor,
  deriveLevel,
  levelColor,
  radarPoint,
  truncateLabel,
} from './posterLayout'
import { formatScore, type PosterAssets, type PosterCanvasContext } from './posterCanvas'
import {
  POSTER_TL_CTA,
  POSTER_TL_CTA_HINT,
  POSTER_TL_CTA_TEXT,
  POSTER_TL_DETAIL,
  POSTER_TL_HEIGHT,
  POSTER_TL_HERO,
  POSTER_TL_LEVEL_LABEL,
  POSTER_TL_MARGIN_X,
  POSTER_TL_SUBTAGLINE,
  POSTER_TL_TAGLINE,
  POSTER_TL_WATERMARK,
  POSTER_TL_WIDTH,
  POSTER_TL_ZONES,
  tlQrLeftX,
} from './posterTimelineLayout'

export { POSTER_TL_WIDTH, POSTER_TL_HEIGHT }

export interface DrawPosterTimelineResult {
  accentColor: string
  scoreText: string
  levelText: string
  issuesDrawn: number
}

export function drawPosterTimeline(
  ctx: PosterCanvasContext,
  input: PosterInput,
  assets: PosterAssets = { thumbnailImage: null, wxaCodeImage: null },
): DrawPosterTimelineResult {
  const level = input.scoreLevel ?? deriveLevel(input.overallScore)
  const accent = levelColor(level)

  drawBackground(ctx, accent)
  drawHero(ctx, input, level, accent)
  const issuesDrawn = drawDetail(ctx, input, accent)
  drawCta(ctx, assets.wxaCodeImage, accent)

  return {
    accentColor: accent,
    scoreText: formatScore(input.overallScore),
    levelText: level ? POSTER_TL_LEVEL_LABEL[level] : '--',
    issuesDrawn,
  }
}

function drawBackground(ctx: PosterCanvasContext, accent: string): void {
  ctx.fillStyle = POSTER_COLORS.white
  ctx.fillRect(0, 0, POSTER_TL_WIDTH, POSTER_TL_HEIGHT)

  ctx.fillStyle = POSTER_COLORS.primary
  ctx.fillRect(0, POSTER_TL_ZONES.hero.yStart, POSTER_TL_WIDTH, POSTER_TL_ZONES.hero.yEnd)

  ctx.fillStyle = accent
  ctx.globalAlpha = 0.1
  ctx.fillRect(0, POSTER_TL_ZONES.hero.yEnd - 4, POSTER_TL_WIDTH, 4)
  ctx.globalAlpha = 1
}

function drawHero(
  ctx: PosterCanvasContext,
  input: PosterInput,
  level: AnalysisScoreLevel | null,
  accent: string,
): void {
  ctx.textAlign = 'center'
  ctx.fillStyle = POSTER_COLORS.white
  ctx.font = `700 ${POSTER_TL_HERO.taglineFontSize}px sans-serif`
  ctx.textBaseline = 'top'
  ctx.fillText(POSTER_TL_TAGLINE, POSTER_TL_WIDTH / 2, POSTER_TL_HERO.taglineY)

  ctx.font = `400 ${POSTER_TL_HERO.subtaglineFontSize}px sans-serif`
  ctx.fillStyle = '#dee2ff'
  ctx.fillText(POSTER_TL_SUBTAGLINE, POSTER_TL_WIDTH / 2, POSTER_TL_HERO.subtaglineY)

  ctx.fillStyle = accent === POSTER_COLORS.primary ? POSTER_COLORS.gold : accent
  ctx.font = `800 ${POSTER_TL_HERO.scoreFontSize}px sans-serif`
  ctx.textBaseline = 'middle'
  ctx.fillText(formatScore(input.overallScore), POSTER_TL_WIDTH / 2, POSTER_TL_HERO.scoreCenterY)

  const levelText = level ? POSTER_TL_LEVEL_LABEL[level] : '待评级'
  drawLevelChip(ctx, POSTER_TL_WIDTH / 2, POSTER_TL_HERO.levelChipY, levelText, accent)

  ctx.fillStyle = '#c5cae9'
  ctx.font = `400 ${POSTER_TL_HERO.metaFontSize}px sans-serif`
  ctx.textBaseline = 'top'
  const meta = `${truncateLabel(input.clubLabel, 12)} · ${truncateLabel(input.cameraAngleLabel, 10)}`
  ctx.fillText(meta, POSTER_TL_WIDTH / 2, POSTER_TL_HERO.metaY)
}

function drawLevelChip(
  ctx: PosterCanvasContext,
  centerX: number,
  centerY: number,
  text: string,
  accent: string,
): void {
  const paddingX = 28
  const chipH = 52
  const textWidth = text.length * (POSTER_TL_HERO.levelChipFontSize * 0.9)
  const chipW = textWidth + paddingX * 2
  const x = centerX - chipW / 2
  const y = centerY - chipH / 2

  ctx.fillStyle = accent
  ctx.fillRect(x, y, chipW, chipH)
  ctx.fillStyle = POSTER_COLORS.white
  ctx.font = `700 ${POSTER_TL_HERO.levelChipFontSize}px sans-serif`
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.fillText(text, centerX, centerY)
}

function drawDetail(
  ctx: PosterCanvasContext,
  input: PosterInput,
  accent: string,
): number {
  drawRadar(ctx, input.phaseScores, input.phaseLabels, accent)
  return drawIssues(ctx, input.topIssues, accent)
}

function drawRadar(
  ctx: PosterCanvasContext,
  phaseScores: number[],
  phaseLabels: string[],
  accent: string,
): void {
  const centerX = POSTER_TL_WIDTH / 2
  const centerY = POSTER_TL_DETAIL.radarCenterY
  const radius = POSTER_TL_DETAIL.radarRadius
  const labelRadius = radius + 28
  const axisCount = phaseScores.length || 6

  ctx.lineWidth = 1
  ctx.strokeStyle = POSTER_COLORS.border
  for (let ring = 1; ring <= 5; ring += 1) {
    ctx.beginPath()
    for (let i = 0; i < axisCount; i += 1) {
      const p = radarPoint(centerX, centerY, radius, i, axisCount, ring / 5)
      if (i === 0) ctx.moveTo(p.x, p.y)
      else ctx.lineTo(p.x, p.y)
    }
    ctx.closePath()
    ctx.stroke()
  }

  for (let i = 0; i < axisCount; i += 1) {
    const p = radarPoint(centerX, centerY, radius, i, axisCount, 1)
    ctx.beginPath()
    ctx.moveTo(centerX, centerY)
    ctx.lineTo(p.x, p.y)
    ctx.stroke()
  }

  if (phaseScores.length > 0) {
    ctx.fillStyle = accent
    ctx.globalAlpha = 0.16
    ctx.strokeStyle = accent
    ctx.lineWidth = 3
    ctx.beginPath()
    for (let i = 0; i < phaseScores.length; i += 1) {
      const ratio = Math.max(0, Math.min(1, (phaseScores[i] ?? 0) / 100))
      const p = radarPoint(centerX, centerY, radius, i, phaseScores.length, ratio)
      if (i === 0) ctx.moveTo(p.x, p.y)
      else ctx.lineTo(p.x, p.y)
    }
    ctx.closePath()
    ctx.fill()
    ctx.globalAlpha = 1
    ctx.stroke()
  }

  ctx.fillStyle = POSTER_COLORS.ink
  ctx.font = '500 22px sans-serif'
  for (let i = 0; i < phaseLabels.length; i += 1) {
    const anchor = axisLabelAnchor(centerX, centerY, labelRadius, i, phaseLabels.length)
    ctx.textAlign = anchor.align
    ctx.textBaseline = anchor.baseline
    ctx.fillText(truncateLabel(phaseLabels[i] ?? '', 4), anchor.x, anchor.y)
  }
}

function drawIssues(ctx: PosterCanvasContext, issues: string[], accent: string): number {
  ctx.fillStyle = POSTER_COLORS.ink
  ctx.font = `700 ${POSTER_TL_DETAIL.issuesTitleFontSize}px sans-serif`
  ctx.textAlign = 'left'
  ctx.textBaseline = 'top'
  ctx.fillText('主要问题', POSTER_TL_MARGIN_X, POSTER_TL_DETAIL.issuesTitleY)

  const items = issues.slice(0, POSTER_TL_DETAIL.issuesMax)
  for (let i = 0; i < items.length; i += 1) {
    const y = POSTER_TL_DETAIL.issuesFirstY + i * POSTER_TL_DETAIL.issuesLineHeight
    ctx.fillStyle = accent
    ctx.fillRect(POSTER_TL_MARGIN_X, y + 8, 10, 10)
    ctx.fillStyle = POSTER_COLORS.inkSoft
    ctx.font = `500 ${POSTER_TL_DETAIL.issuesFontSize}px sans-serif`
    ctx.fillText(
      truncateLabel(items[i], 16),
      POSTER_TL_MARGIN_X + 24,
      y,
      POSTER_TL_WIDTH - POSTER_TL_MARGIN_X * 2 - 24,
    )
  }

  if (items.length === 0) {
    ctx.fillStyle = POSTER_COLORS.inkMuted
    ctx.font = `500 ${POSTER_TL_DETAIL.issuesFontSize}px sans-serif`
    ctx.fillText('暂未识别到突出问题，继续保持！', POSTER_TL_MARGIN_X, POSTER_TL_DETAIL.issuesFirstY)
  }

  return items.length
}

function readImageNaturalSize(image: unknown): { width: number; height: number } {
  const img = image as { width?: number; height?: number }
  const width = Number(img?.width)
  const height = Number(img?.height)
  if (width > 0 && height > 0) return { width, height }
  return { width: POSTER_WXA_CODE_SRC_SIZE, height: POSTER_WXA_CODE_SRC_SIZE }
}

function drawCta(ctx: PosterCanvasContext, wxaImage: unknown | null, _accent: string): void {
  ctx.textAlign = 'center'
  ctx.fillStyle = POSTER_COLORS.ink
  ctx.font = `600 ${POSTER_TL_CTA.ctaTextFontSize}px sans-serif`
  ctx.textBaseline = 'top'
  ctx.fillText(POSTER_TL_CTA_TEXT, POSTER_TL_WIDTH / 2, POSTER_TL_CTA.ctaTextY)

  ctx.fillStyle = POSTER_COLORS.inkSoft
  ctx.font = `400 ${POSTER_TL_CTA.ctaHintFontSize}px sans-serif`
  ctx.fillText(POSTER_TL_CTA_HINT, POSTER_TL_WIDTH / 2, POSTER_TL_CTA.ctaHintY)

  const qrSize = POSTER_TL_CTA.qrSize
  const x = tlQrLeftX()
  const y = POSTER_TL_CTA.qrTop

  ctx.fillStyle = POSTER_COLORS.white
  ctx.fillRect(x - 10, y - 10, qrSize + 20, qrSize + 20)
  ctx.lineWidth = 2
  ctx.strokeStyle = POSTER_COLORS.border
  ctx.strokeRect?.(x - 10, y - 10, qrSize + 20, qrSize + 20)

  if (wxaImage) {
    const { width: srcW, height: srcH } = readImageNaturalSize(wxaImage)
    ctx.drawImage(wxaImage, 0, 0, srcW, srcH, x, y, qrSize, qrSize)
  } else {
    ctx.fillStyle = '#f3f4f6'
    ctx.fillRect(x, y, qrSize, qrSize)
    ctx.fillStyle = POSTER_COLORS.inkMuted
    ctx.font = '500 28px sans-serif'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillText('扫码体验', x + qrSize / 2, y + qrSize / 2)
  }

  ctx.fillStyle = POSTER_COLORS.inkMuted
  ctx.font = `400 ${POSTER_TL_CTA.watermarkFontSize}px sans-serif`
  ctx.textAlign = 'center'
  ctx.textBaseline = 'bottom'
  ctx.fillText(POSTER_TL_WATERMARK, POSTER_TL_WIDTH / 2, POSTER_TL_CTA.watermarkY)
}
