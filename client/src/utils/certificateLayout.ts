/**
 * M11-05 · 阶段通关证书 Canvas 版式（复用 M5 海报品牌色）。
 */

export const CERT_WIDTH = 750
export const CERT_HEIGHT = 1060

/** 与 posterLayout / app.scss 对齐 */
export const CERT_COLORS = {
  primary: '#1a237e',
  primaryDark: '#0d1657',
  gold: '#c9a227',
  mint: '#00d084',
  white: '#ffffff',
  textMuted: '#5c6bc0',
} as const

export interface StageCertificateInput {
  holderName: string
  courseTitle: string
  stage: number
  stageTitle: string
  badgeLabel: string
  issuedAtLabel: string
}

export const STAGE_TITLES: Record<number, string> = {
  1: '第 1 阶 · 入门',
  2: '第 2 阶 · 基础',
  3: '第 3 阶 · 进阶',
  4: '第 4 阶 · 整合',
  5: '第 5 阶 · 精修',
  6: '第 6 阶 · 高阶',
  7: '第 7 阶 · 大师',
}

export function formatCertificateIssuedAt(iso: string | null | undefined): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso.slice(0, 10)
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}年${m}月${day}日`
}
