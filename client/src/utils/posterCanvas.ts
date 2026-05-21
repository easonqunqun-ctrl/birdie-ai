/**
 * 分享海报 Canvas 2D 绘制（Q-C1）。
 *
 * 入参 `ctx` 是任意 Canvas 2D Context（小程序里由 `Canvas.getContext('2d')` 给出；
 * 单测里可以传 mock）。
 *
 * 海报版式（750×1334）：
 *  - 顶部品牌区（领翼golf · LOGO · slogan）
 *  - 大分数 + 评级徽章
 *  - 6D 雷达图（5 圈背景 + 数据多边形）
 *  - 主要问题列表（最多 3 条）
 *  - 小程序码 + 「扫码查看完整报告」
 *  - 底部水印
 */

import type { AnalysisScoreLevel } from '@/types/analysis'
import {
  POSTER_COLORS,
  POSTER_HEIGHT,
  POSTER_WIDTH,
  PosterInput,
  axisLabelAnchor,
  deriveLevel,
  levelColor,
  radarPoint,
  truncateLabel,
} from './posterLayout'

/** 评级 → 中文标题（与 SCORE_LEVEL_META.label 对齐） */
export const POSTER_LEVEL_LABEL: Record<AnalysisScoreLevel, string> = {
  excellent: '专业水准',
  great: '进阶球员',
  good: '良好',
  fair: '及格',
  needs_improvement: '待改进',
}

/** Canvas 2D 子集（小程序 `Canvas.getContext('2d')` 与 W3C HTMLCanvasContext 兼容） */
export interface PosterCanvasContext {
  fillStyle: string | CanvasGradient | CanvasPattern
  strokeStyle: string | CanvasGradient | CanvasPattern
  font: string
  textAlign: CanvasTextAlign
  textBaseline: CanvasTextBaseline
  lineWidth: number
  globalAlpha: number
  fillRect: (x: number, y: number, w: number, h: number) => void
  strokeRect?: (x: number, y: number, w: number, h: number) => void
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
  drawImage: (
    image: unknown,
    sx: number,
    sy: number,
    sw?: number,
    sh?: number,
    dx?: number,
    dy?: number,
    dw?: number,
    dh?: number,
  ) => void
  save: () => void
  restore: () => void
}

export interface PosterAssets {
  /** 6D 缩略图 Image 对象（已 load）；null 表示无图，画占位灰底 */
  thumbnailImage: unknown | null
  /** 小程序码 Image 对象（已 load）；null 表示无图，画占位灰底 */
  wxaCodeImage: unknown | null
}

/**
 * 主绘制入口。
 * 返回值仅供单测断言（实际副作用全在 ctx 上）。
 */
export interface DrawPosterResult {
  /** 绘制时使用的主色 */
  accentColor: string
  /** 渲染的分数文本（缺分时为 "--"） */
  scoreText: string
  /** 渲染的评级中文文本 */
  levelText: string
  /** 实际绘制的 issue 行数 */
  issuesDrawn: number
}

export function drawPoster(
  ctx: PosterCanvasContext,
  input: PosterInput,
  assets: PosterAssets = { thumbnailImage: null, wxaCodeImage: null },
): DrawPosterResult {
  const level = input.scoreLevel ?? deriveLevel(input.overallScore)
  const accent = levelColor(level)

  drawBackground(ctx, accent)
  drawHeader(ctx)
  drawScoreCard(ctx, input.overallScore, level, accent, input.clubLabel, input.cameraAngleLabel)
  drawRadar(ctx, input.phaseScores, input.phaseLabels, accent)
  const issuesDrawn = drawIssues(ctx, input.topIssues, accent)
  drawWxaCode(ctx, assets.wxaCodeImage, accent)
  drawFooter(ctx)

  return {
    accentColor: accent,
    scoreText: formatScore(input.overallScore),
    levelText: level ? POSTER_LEVEL_LABEL[level] : '--',
    issuesDrawn,
  }
}

export function formatScore(score: number | null | undefined): string {
  if (score === null || score === undefined || Number.isNaN(score)) return '--'
  return Math.round(score).toString()
}

// ---------- 分段绘制 ----------

function drawBackground(ctx: PosterCanvasContext, accent: string): void {
  ctx.fillStyle = POSTER_COLORS.white
  ctx.fillRect(0, 0, POSTER_WIDTH, POSTER_HEIGHT)

  ctx.fillStyle = POSTER_COLORS.primary
  ctx.fillRect(0, 0, POSTER_WIDTH, 220)

  ctx.fillStyle = accent
  ctx.globalAlpha = 0.12
  ctx.fillRect(0, 220, POSTER_WIDTH, 6)
  ctx.globalAlpha = 1
}

function drawHeader(ctx: PosterCanvasContext): void {
  ctx.fillStyle = POSTER_COLORS.white
  ctx.textAlign = 'left'
  ctx.textBaseline = 'middle'

  ctx.font = '700 44px sans-serif'
  ctx.fillText('领翼golf', 60, 90)

  ctx.font = '400 26px sans-serif'
  ctx.fillStyle = '#dee2ff'
  ctx.fillText('AI 高尔夫私教 · 挥杆报告', 60, 145)

  ctx.font = '500 22px sans-serif'
  ctx.fillStyle = POSTER_COLORS.gold
  ctx.textAlign = 'right'
  ctx.fillText('扫码挑战我', POSTER_WIDTH - 60, 90)
}

function drawScoreCard(
  ctx: PosterCanvasContext,
  score: number | null,
  level: AnalysisScoreLevel | null,
  accent: string,
  clubLabel: string,
  cameraLabel: string,
): void {
  const cardX = 60
  const cardY = 280
  const cardW = POSTER_WIDTH - cardX * 2
  const cardH = 240

  ctx.fillStyle = POSTER_COLORS.white
  ctx.fillRect(cardX, cardY, cardW, cardH)
  ctx.lineWidth = 2
  ctx.strokeStyle = POSTER_COLORS.border
  ctx.strokeRect?.(cardX, cardY, cardW, cardH)

  ctx.textAlign = 'left'
  ctx.textBaseline = 'top'
  ctx.fillStyle = POSTER_COLORS.inkSoft
  ctx.font = '500 28px sans-serif'
  ctx.fillText('综合得分', cardX + 40, cardY + 36)

  ctx.fillStyle = accent
  ctx.font = '800 130px sans-serif'
  ctx.textBaseline = 'alphabetic'
  ctx.fillText(formatScore(score), cardX + 40, cardY + 180)

  ctx.fillStyle = POSTER_COLORS.inkMuted
  ctx.font = '500 26px sans-serif'
  ctx.textBaseline = 'alphabetic'
  ctx.fillText('/100', cardX + 40 + scoreWidthEstimate(score), cardY + 180)

  const badgeText = level ? POSTER_LEVEL_LABEL[level] : '待评级'
  drawLevelBadge(ctx, cardX + cardW - 40, cardY + 36, badgeText, accent)

  ctx.fillStyle = POSTER_COLORS.inkSoft
  ctx.font = '400 24px sans-serif'
  ctx.textBaseline = 'alphabetic'
  ctx.textAlign = 'right'
  const meta = `${truncateLabel(clubLabel, 10)} · ${truncateLabel(cameraLabel, 10)}`
  ctx.fillText(meta, cardX + cardW - 40, cardY + cardH - 36)
}

function scoreWidthEstimate(score: number | null | undefined): number {
  const txt = formatScore(score)
  return txt.length * 70 + 10
}

function drawLevelBadge(
  ctx: PosterCanvasContext,
  rightX: number,
  topY: number,
  text: string,
  accent: string,
): void {
  const padding = 24
  const badgeH = 56
  const textWidth = text.length * 28
  const badgeW = textWidth + padding * 2
  const x = rightX - badgeW
  const y = topY

  ctx.fillStyle = accent
  ctx.fillRect(x, y, badgeW, badgeH)

  ctx.fillStyle = POSTER_COLORS.white
  ctx.font = '700 28px sans-serif'
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.fillText(text, x + badgeW / 2, y + badgeH / 2)
}

function drawRadar(
  ctx: PosterCanvasContext,
  phaseScores: number[],
  phaseLabels: string[],
  accent: string,
): void {
  const centerX = POSTER_WIDTH / 2
  const centerY = 720
  const radius = 200
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

  ctx.strokeStyle = POSTER_COLORS.border
  for (let i = 0; i < axisCount; i += 1) {
    const p = radarPoint(centerX, centerY, radius, i, axisCount, 1)
    ctx.beginPath()
    ctx.moveTo(centerX, centerY)
    ctx.lineTo(p.x, p.y)
    ctx.stroke()
  }

  if (phaseScores.length > 0) {
    ctx.fillStyle = accent
    ctx.globalAlpha = 0.18
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
    const anchor = axisLabelAnchor(centerX, centerY, radius + 28, i, phaseLabels.length)
    ctx.textAlign = anchor.align
    ctx.textBaseline = anchor.baseline
    ctx.fillText(truncateLabel(phaseLabels[i] ?? '', 4), anchor.x, anchor.y)
  }
}

function drawIssues(
  ctx: PosterCanvasContext,
  issues: string[],
  accent: string,
): number {
  const top = 1000
  const left = 60
  const right = POSTER_WIDTH - 60
  const lineH = 56
  const maxLines = 3

  ctx.fillStyle = POSTER_COLORS.ink
  ctx.font = '700 30px sans-serif'
  ctx.textAlign = 'left'
  ctx.textBaseline = 'middle'
  ctx.fillText('主要问题', left, top)

  const items = issues.slice(0, maxLines)
  for (let i = 0; i < items.length; i += 1) {
    const y = top + 50 + i * lineH

    ctx.fillStyle = accent
    ctx.fillRect(left, y - 4, 8, 8)

    ctx.fillStyle = POSTER_COLORS.inkSoft
    ctx.font = '500 26px sans-serif'
    ctx.textAlign = 'left'
    ctx.textBaseline = 'middle'
    const maxChars = 18
    ctx.fillText(truncateLabel(items[i], maxChars), left + 28, y, right - left - 28)
  }

  if (items.length === 0) {
    ctx.fillStyle = POSTER_COLORS.inkMuted
    ctx.font = '500 26px sans-serif'
    ctx.fillText('暂未识别到突出问题，继续保持！', left, top + 60)
  }

  return items.length
}

function drawWxaCode(
  ctx: PosterCanvasContext,
  wxaImage: unknown | null,
  accent: string,
): void {
  const size = 200
  const x = POSTER_WIDTH - size - 60
  const y = POSTER_HEIGHT - size - 120

  ctx.fillStyle = POSTER_COLORS.white
  ctx.fillRect(x - 10, y - 10, size + 20, size + 20)
  ctx.lineWidth = 2
  ctx.strokeStyle = POSTER_COLORS.border
  ctx.strokeRect?.(x - 10, y - 10, size + 20, size + 20)

  if (wxaImage) {
    ctx.drawImage(wxaImage, 0, 0, size, size, x, y, size, size)
  } else {
    ctx.fillStyle = POSTER_COLORS.border
    ctx.fillRect(x, y, size, size)
  }

  ctx.fillStyle = POSTER_COLORS.ink
  ctx.font = '600 28px sans-serif'
  ctx.textAlign = 'left'
  ctx.textBaseline = 'top'
  ctx.fillText('扫码看完整报告', 60, y + 20)

  ctx.fillStyle = POSTER_COLORS.inkSoft
  ctx.font = '400 24px sans-serif'
  ctx.fillText('AI 私教 · 拍一段挥杆视频', 60, y + 70)

  ctx.fillStyle = accent
  ctx.font = '500 22px sans-serif'
  ctx.fillText('打开「领翼golf」立刻挑战', 60, y + 120)
}

function drawFooter(ctx: PosterCanvasContext): void {
  ctx.fillStyle = POSTER_COLORS.inkMuted
  ctx.font = '400 22px sans-serif'
  ctx.textAlign = 'center'
  ctx.textBaseline = 'bottom'
  ctx.fillText('AI 仅供训练参考 · 实战以教练指导为准', POSTER_WIDTH / 2, POSTER_HEIGHT - 40)
}
