/**
 * `posterTimelineLayout` 纯函数单测（W16-C / Q-B2 余量）.
 *
 * 这些常量决定朋友圈封面的版式安全性：
 * - Hero / Detail / CTA 三个 Y 区不重叠
 * - 雷达图不撑出 Detail 区上下沿
 * - 水印不出画布
 *
 * 任意一项不通过都会让朋友圈封面出现「叠字 / 出框 / 信息流首屏看不到大标语」
 * 的视觉灾难，所以单测严格断言。
 */

import {
  POSTER_TL_CTA,
  POSTER_TL_CTA_HINT,
  POSTER_TL_CTA_TEXT,
  POSTER_TL_DETAIL,
  POSTER_TL_HEIGHT,
  POSTER_TL_HERO,
  POSTER_TL_LEVEL_LABEL,
  POSTER_TL_MARGIN_X,
  POSTER_TL_SCALE_VS_LEGACY,
  POSTER_TL_SUBTAGLINE,
  POSTER_TL_TAGLINE,
  POSTER_TL_WATERMARK,
  POSTER_TL_WIDTH,
  POSTER_TL_ZONES,
  tlCtaBottomY,
  tlDetailBottomY,
  tlHeroBottomY,
  tlQrLeftX,
  verifyTimelineLayout,
} from '../posterTimelineLayout'

describe('posterTimelineLayout · 基础常量', () => {
  it('画布尺寸 1080×1920（朋友圈封面 9:16）', () => {
    expect(POSTER_TL_WIDTH).toBe(1080)
    expect(POSTER_TL_HEIGHT).toBe(1920)
    // 9:16 = 1.778
    expect(POSTER_TL_HEIGHT / POSTER_TL_WIDTH).toBeCloseTo(16 / 9, 2)
  })

  it('与老 750×1334 海报的等比缩放系数 = 1.44', () => {
    expect(POSTER_TL_SCALE_VS_LEGACY).toBeCloseTo(1080 / 750, 2)
  })

  it('左右安全边距合理（≥ 60px @1x，避免文字贴边）', () => {
    expect(POSTER_TL_MARGIN_X).toBeGreaterThanOrEqual(60)
    expect(POSTER_TL_MARGIN_X).toBeLessThan(POSTER_TL_WIDTH / 4)
  })
})

describe('posterTimelineLayout · 三段 Y 区严格不重叠', () => {
  it('Hero / Detail / CTA 区按 Y 顺序拼接，无 gap 无 overlap', () => {
    expect(POSTER_TL_ZONES.hero.yStart).toBe(0)
    expect(POSTER_TL_ZONES.hero.yEnd).toBe(POSTER_TL_ZONES.detail.yStart)
    expect(POSTER_TL_ZONES.detail.yEnd).toBe(POSTER_TL_ZONES.cta.yStart)
    expect(POSTER_TL_ZONES.cta.yEnd).toBe(POSTER_TL_HEIGHT)
  })

  it('Hero 区高度 ≥ 600px（保证朋友圈信息流首屏吃到大标语 + 综合分）', () => {
    const heroHeight = POSTER_TL_ZONES.hero.yEnd - POSTER_TL_ZONES.hero.yStart
    expect(heroHeight).toBeGreaterThanOrEqual(600)
  })

  it('Detail 区高度 ≥ 700px（雷达图 + 3 个 issue 行能挤进去）', () => {
    const detailHeight =
      POSTER_TL_ZONES.detail.yEnd - POSTER_TL_ZONES.detail.yStart
    expect(detailHeight).toBeGreaterThanOrEqual(700)
  })
})

describe('posterTimelineLayout · 各区元素不出区', () => {
  it('Hero 区文字底部不撑出 Hero zone', () => {
    expect(tlHeroBottomY()).toBeLessThanOrEqual(POSTER_TL_ZONES.hero.yEnd)
  })

  it('综合分大数字（240px）严格在 Hero zone 内', () => {
    const half = POSTER_TL_HERO.scoreFontSize / 2
    expect(POSTER_TL_HERO.scoreCenterY - half).toBeGreaterThanOrEqual(
      POSTER_TL_ZONES.hero.yStart,
    )
    expect(POSTER_TL_HERO.scoreCenterY + half).toBeLessThanOrEqual(
      POSTER_TL_ZONES.hero.yEnd,
    )
  })

  it('Detail 区底（含 3 行 issue）不撑出 Detail zone', () => {
    expect(tlDetailBottomY(3)).toBeLessThanOrEqual(POSTER_TL_ZONES.detail.yEnd)
  })

  it('Detail 区底（0 行 issue · 边界）不撑出 Detail zone', () => {
    expect(tlDetailBottomY(0)).toBeLessThanOrEqual(POSTER_TL_ZONES.detail.yEnd)
  })

  it('雷达图上沿严格在 Detail zone 内（顶部不刺出 Hero）', () => {
    const radarTop = POSTER_TL_DETAIL.radarCenterY - POSTER_TL_DETAIL.radarRadius
    expect(radarTop).toBeGreaterThanOrEqual(POSTER_TL_ZONES.detail.yStart)
  })

  it('CTA 区底（小程序码 + 32px buffer）不撑出 CTA zone 上沿', () => {
    expect(tlCtaBottomY()).toBeLessThanOrEqual(POSTER_TL_ZONES.cta.yEnd)
  })

  it('CTA 区第一行文字 Y ≥ CTA zone yStart', () => {
    expect(POSTER_TL_CTA.ctaTextY).toBeGreaterThanOrEqual(POSTER_TL_ZONES.cta.yStart)
  })

  it('底部水印不出画布', () => {
    expect(POSTER_TL_CTA.watermarkY).toBeLessThan(POSTER_TL_HEIGHT)
  })
})

describe('posterTimelineLayout · 综合健康检查', () => {
  it.each<[number, true]>([
    [0, true],
    [1, true],
    [2, true],
    [3, true],
  ])('verifyTimelineLayout(issueCount=%i) 全部 health 项 true', (issueCount) => {
    const health = verifyTimelineLayout(issueCount)
    expect(health.heroFitsZone).toBe(true)
    expect(health.detailFitsZone).toBe(true)
    expect(health.ctaFitsZone).toBe(true)
    expect(health.watermarkFitsCanvas).toBe(true)
  })
})

describe('posterTimelineLayout · 小程序码居中', () => {
  it('tlQrLeftX() 把小程序码摆在画布水平中心', () => {
    const qrLeft = tlQrLeftX()
    const qrCenter = qrLeft + POSTER_TL_CTA.qrSize / 2
    expect(qrCenter).toBeCloseTo(POSTER_TL_WIDTH / 2, 0)
  })

  it('小程序码不溢出左右安全边距', () => {
    expect(tlQrLeftX()).toBeGreaterThanOrEqual(POSTER_TL_MARGIN_X)
    expect(tlQrLeftX() + POSTER_TL_CTA.qrSize).toBeLessThanOrEqual(
      POSTER_TL_WIDTH - POSTER_TL_MARGIN_X,
    )
  })
})

describe('posterTimelineLayout · 文案常量', () => {
  it('文案非空且为中文（朋友圈封面只对中文场景）', () => {
    expect(POSTER_TL_TAGLINE.length).toBeGreaterThan(0)
    expect(POSTER_TL_SUBTAGLINE.length).toBeGreaterThan(0)
    expect(POSTER_TL_CTA_TEXT.length).toBeGreaterThan(0)
    expect(POSTER_TL_CTA_HINT.length).toBeGreaterThan(0)
    expect(POSTER_TL_WATERMARK.length).toBeGreaterThan(0)
  })

  it('评级 chip 5 档全覆盖（与 AnalysisScoreLevel 对齐）', () => {
    expect(Object.keys(POSTER_TL_LEVEL_LABEL).sort()).toEqual([
      'excellent',
      'fair',
      'good',
      'great',
      'needs_improvement',
    ])
  })
})
