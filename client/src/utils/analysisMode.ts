/**
 * P2-M10-01/02 · 分析模式与球杆联动校验（params 页与提交前复用）
 */

import type { AnalysisMode } from '@/types/analysis'
import type { ClubType } from '@/types/api'
import { CHIPPING_CLUB_HINT } from '@/constants/chippingLabels'

/** 切换 mode 时建议的默认 club_type */
export function defaultClubTypeForMode(mode: AnalysisMode): ClubType {
  if (mode === 'putting') return 'putter'
  if (mode === 'chipping') return 'wedge'
  return 'iron_7'
}

/** mode 与 club_type 是否匹配（与 ai_engine 50123 规则对齐） */
export function isModeClubCompatible(mode: AnalysisMode, clubType: ClubType): boolean {
  if (mode === 'putting') return clubType === 'putter'
  if (mode === 'chipping') {
    return CHIPPING_CLUB_HINT.includes(clubType as (typeof CHIPPING_CLUB_HINT)[number])
  }
  return clubType !== 'putter'
}

/** 提交前本地校验；不匹配时返回提示文案 */
export function modeClubMismatchHint(mode: AnalysisMode, clubType: ClubType): string | null {
  if (isModeClubCompatible(mode, clubType)) return null
  if (mode === 'putting') return '推杆分析请选择推杆模式并选 putter 球杆'
  if (mode === 'chipping') return '切杆分析请选择 wedge 或 8/9 号铁'
  return '全挥杆分析请勿选择推杆'
}
