/**
 * 评分分级 UI 映射
 *
 * 与 `backend/app/schemas/analysis.py::score_level()` 严格对齐（5 档）：
 *   excellent (≥90)   — 金色  — 专业水准
 *   great     (≥80)   — 深绿  — 进阶
 *   good      (≥70)   — 蓝色  — 良好
 *   fair      (≥60)   — 橙色  — 及格但有改进空间
 *   needs_improvement (<60) — 红色 — 需要重点改进
 *
 * 色值不直接用 HEX，而是用 CSS 变量；保持和 app.scss Design Tokens 同源。
 */

import type { AnalysisScoreLevel } from '@/types/analysis'

export interface ScoreLevelMeta {
  /** 中文标签 */
  label: string
  /** 一句话总结 */
  caption: string
  /** 关联 CSS 变量（用于徽章背景） */
  cssVar: string
  /** 徽章文字颜色 */
  textCssVar: string
  /** emoji（用于顶部 hero，简化不额外引入 icon） */
  emoji: string
}

export const SCORE_LEVEL_META: Record<AnalysisScoreLevel, ScoreLevelMeta> = {
  excellent: {
    label: '专业水准',
    caption: '非常棒，这一杆接近职业水平',
    cssVar: 'var(--color-gold)',
    textCssVar: 'var(--color-primary-dark)',
    emoji: '🏆',
  },
  great: {
    label: '进阶球员',
    caption: '稳定输出的挥杆，继续保持',
    cssVar: 'var(--color-primary)',
    textCssVar: 'var(--color-on-primary)',
    emoji: '⛳️',
  },
  good: {
    label: '良好',
    caption: '基础不错，还有打磨空间',
    cssVar: '#3b82f6',
    textCssVar: '#ffffff',
    emoji: '👍',
  },
  fair: {
    label: '及格',
    caption: '方向对了，把问题一个个解决',
    cssVar: 'var(--color-warning, #f59e0b)',
    textCssVar: '#ffffff',
    emoji: '💪',
  },
  needs_improvement: {
    label: '待改进',
    caption: '放心，按建议练一周会有明显进步',
    cssVar: 'var(--color-error, #ef4444)',
    textCssVar: '#ffffff',
    emoji: '📈',
  },
}

/** 从综合分数派生 level（前端兜底，正常走 backend.score_level 字段） */
export function scoreLevelFromScore(score: number | null | undefined): AnalysisScoreLevel | null {
  if (score === null || score === undefined) return null
  if (score >= 90) return 'excellent'
  if (score >= 80) return 'great'
  if (score >= 70) return 'good'
  if (score >= 60) return 'fair'
  return 'needs_improvement'
}
