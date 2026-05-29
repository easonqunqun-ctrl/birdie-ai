/**
 * 分享海报 · 朋友圈封面变体（W16-C / Q-B2 余量）
 *
 * 背景
 * ====
 * 现有 750×1334 海报（`posterLayout.ts`）是为「微信好友分享 imageUrl + 保存到相册」
 * 设计的，**信息密度高、布局密集**。
 *
 * 朋友圈封面（cover）的视觉诉求不一样：
 * - **更高更瘦**（1080×1920，9:16 全屏）
 * - **首屏第一眼只看到「评分 + 标语」**——朋友圈信息流只显示卡片**上 1/3** 高度
 * - **下 2/3 留给详情**（6D 雷达 / 主要问题 / 小程序码）——用户点开"查看大图"才看到全貌
 *
 * 所以朋友圈版式不能简单等比放大现有 750×1334，而是**重新分配 Y 锚点**：
 * - 顶部大标题区（0~640px）：标语「我的挥杆 AI 评分」+ 综合分 + 评级 → 信息流首屏吃到
 * - 中部详情区（640~1440px）：6D 雷达 + 关键问题 → 点开看
 * - 底部 CTA（1440~1920px）：扫码引导 + 小程序码
 *
 * 与 750×1334 海报的关系
 * ------------------
 * - **不复用** Y 锚点（视觉重心完全不同）
 * - **复用**色板（`POSTER_COLORS`）/ 文案 token（`POSTER_LEVEL_LABEL`）/ 几何函数（`radarPoint` / `axisLabelAnchor`）
 * - **复用** `drawPoster` 内部分段 helper（drawScoreCard / drawRadar / drawIssues），但改用本文件的锚点
 *
 * 工程范围（W16-C）
 * --------------
 * **本文件就位**：layout 常量 + 锚点纯函数 + 单测
 * **drawPosterTimeline 实现**：另起 `posterCanvasTimeline.ts`（紧跟 layout，但接入 UI 留 W19+）
 * **client UI 入口**：暂不接（产品策划未拍板"朋友圈封面"是否进 v1.x；工具先就位等触发）
 */

import type { AnalysisScoreLevel } from '@/types/analysis'

// ============================================================
// 画布尺寸 · 9:16 朋友圈封面规格（@2x 来自 1080×1920）
// ============================================================

/** 朋友圈封面画布宽（CSS px；Canvas 2D 内部按 dpr 缩放）.
 *
 * 选 1080 而非 1242 的原因：朋友圈封面**实际渲染上限**是 1080×1920（OPPO/小米
 * 安卓主流真机），iOS 端缩放后 1242×2208 也能 fit。1080 是"通用安全分辨率"，
 * 文件体积也比 1242 小 17%（同 PNG 压缩）。
 */
export const POSTER_TL_WIDTH = 1080

/** 朋友圈封面画布高（9:16 = 1.778） */
export const POSTER_TL_HEIGHT = 1920

/** 与 750×1334 老海报的等比缩放系数（约 1.44），文档参考用，不在 layout 里直接用 */
export const POSTER_TL_SCALE_VS_LEGACY = POSTER_TL_WIDTH / 750

// ============================================================
// 三段式 Y 锚点（朋友圈信息流上 1/3 = 0~640，决定首屏视觉重心）
// ============================================================

/** 朋友圈封面三段式 Y 锚点（单位：px @1x） */
export const POSTER_TL_ZONES = {
  /** 上 1/3 = 信息流首屏可见区 · 标语 + 综合分 + 评级 */
  hero: { yStart: 0, yEnd: 640 },
  /** 中 1/3 = 详情区 · 6D 雷达 + 主要问题 */
  detail: { yStart: 640, yEnd: 1440 },
  /** 下 1/3 = CTA 区 · 扫码 + 小程序码 + 水印 */
  cta: { yStart: 1440, yEnd: POSTER_TL_HEIGHT },
} as const

/** 整体安全边距（左右） */
export const POSTER_TL_MARGIN_X = 80

// ============================================================
// HERO 区版式（标语 + 综合分卡）
// ============================================================

/** HERO 区版式 · 上 1/3 信息流首屏 */
export const POSTER_TL_HERO = {
  /** 标语「我的挥杆 AI 评分」基线 Y（top baseline） */
  taglineY: 90,
  taglineFontSize: 44,
  /** 副标语「来挑战我」基线 Y */
  subtaglineY: 150,
  subtaglineFontSize: 28,
  /** 综合分大数字基线 Y（middle baseline） */
  scoreCenterY: 380,
  scoreFontSize: 240,
  /** 评级 chip 基线 Y（middle baseline） */
  levelChipY: 540,
  levelChipFontSize: 36,
  /** 球杆 + 拍摄角度副标 Y（top baseline） */
  metaY: 590,
  metaFontSize: 24,
} as const

// ============================================================
// DETAIL 区版式（6D 雷达 + 主要问题）
// ============================================================

/** DETAIL 区版式 · 中 1/3 */
export const POSTER_TL_DETAIL = {
  /** 6D 雷达图中心 Y（middle baseline） */
  radarCenterY: 920,
  /** 6D 雷达图半径（含轴标签预留） */
  radarRadius: 200,
  /** 「主要问题」标题 Y（top baseline） */
  issuesTitleY: 1180,
  issuesTitleFontSize: 32,
  /** 第一行 issue Y（top baseline） */
  issuesFirstY: 1240,
  issuesLineHeight: 56,
  issuesFontSize: 26,
  issuesMax: 3,
} as const

// ============================================================
// CTA 区版式（扫码引导 + 小程序码 + 水印）
// ============================================================

/** CTA 区版式 · 下 1/3 */
export const POSTER_TL_CTA = {
  /** 「扫码挑战我」副标 Y（top baseline） */
  ctaTextY: 1500,
  ctaTextFontSize: 36,
  /** 「同水平用户对比」slogan Y */
  ctaHintY: 1560,
  ctaHintFontSize: 24,
  /** 小程序码画布起点（左上角） · 居中 */
  qrSize: 240,
  qrTop: 1620,
  /** 底部水印 Y（bottom baseline） */
  watermarkY: POSTER_TL_HEIGHT - 36,
  watermarkFontSize: 22,
} as const

// ============================================================
// 朋友圈封面专属小程序码居中锚点
// ============================================================

/** 小程序码绘制起点 X（居中） */
export function tlQrLeftX(): number {
  return (POSTER_TL_WIDTH - POSTER_TL_CTA.qrSize) / 2
}

// ============================================================
// 单测可断言的几何健康检查
// ============================================================

/** Hero 区底（最后一个文字底部 Y） */
export function tlHeroBottomY(): number {
  return POSTER_TL_HERO.metaY + POSTER_TL_HERO.metaFontSize + 8
}

/** Detail 区底（含 issues 实际行数） */
export function tlDetailBottomY(issueCount: number): number {
  const n = Math.min(Math.max(issueCount, 0), POSTER_TL_DETAIL.issuesMax)
  return (
    POSTER_TL_DETAIL.issuesFirstY +
    n * POSTER_TL_DETAIL.issuesLineHeight +
    16
  )
}

/** CTA 区底（不含底部水印基线） */
export function tlCtaBottomY(): number {
  return POSTER_TL_CTA.qrTop + POSTER_TL_CTA.qrSize + 32
}

/** 整张海报的安全验证：三段 Y 锚点不重叠 */
export interface TimelineLayoutHealth {
  heroFitsZone: boolean
  detailFitsZone: boolean
  ctaFitsZone: boolean
  watermarkFitsCanvas: boolean
}

export function verifyTimelineLayout(issueCount: number): TimelineLayoutHealth {
  const heroBottom = tlHeroBottomY()
  const detailBottom = tlDetailBottomY(issueCount)
  const ctaBottom = tlCtaBottomY()
  return {
    heroFitsZone: heroBottom <= POSTER_TL_ZONES.hero.yEnd,
    detailFitsZone:
      detailBottom <= POSTER_TL_ZONES.detail.yEnd
      && POSTER_TL_DETAIL.radarCenterY - POSTER_TL_DETAIL.radarRadius >= POSTER_TL_ZONES.detail.yStart,
    ctaFitsZone:
      ctaBottom <= POSTER_TL_ZONES.cta.yEnd
      && POSTER_TL_CTA.ctaTextY >= POSTER_TL_ZONES.cta.yStart,
    watermarkFitsCanvas: POSTER_TL_CTA.watermarkY < POSTER_TL_HEIGHT,
  }
}

// ============================================================
// 朋友圈封面副标语文案（不接 i18n，朋友圈仅中文场景）
// ============================================================

export const POSTER_TL_TAGLINE = '我的挥杆 AI 评分'
export const POSTER_TL_SUBTAGLINE = '同水平用户对比 · 来挑战我'
export const POSTER_TL_CTA_TEXT = '扫码挑战我'
export const POSTER_TL_CTA_HINT = 'AI 私教 · 一键诊断挥杆'
export const POSTER_TL_WATERMARK = '领翼golf · AI 仅供训练参考 · 实战以教练指导为准'

/** 评级 chip 中文短标，与 POSTER_LEVEL_LABEL 同源（避免循环引用，本文件不 import） */
export const POSTER_TL_LEVEL_LABEL: Record<AnalysisScoreLevel, string> = {
  excellent: '出色',
  great: '不错',
  good: '良好',
  fair: '一般',
  needs_improvement: '待提升',
}
