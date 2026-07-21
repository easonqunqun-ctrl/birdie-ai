/**
 * 多挥候选清洗：丢掉近零时长伪段（常被标成「试挥」且 UI 显示 0:00–0:00），
 * 并重算 default_selected_index。
 */

import type { SwingCandidateItem } from '@/types/analysis'

/** 短于此时长（秒）的候选视为噪声，不进入选段页。 */
export const MIN_SWING_CANDIDATE_DURATION_SEC = 0.6

export function swingCandidateDurationSec(item: SwingCandidateItem): number {
  return Math.max(0, item.end_time_sec - item.start_time_sec)
}

export function sanitizeSwingCandidates(
  candidates: SwingCandidateItem[],
  defaultSelectedIndex: number,
): { swing_candidates: SwingCandidateItem[]; default_selected_index: number } {
  const filtered = candidates.filter(
    (c) => swingCandidateDurationSec(c) >= MIN_SWING_CANDIDATE_DURATION_SEC,
  )
  if (filtered.length === 0) {
    return {
      swing_candidates: candidates,
      default_selected_index: defaultSelectedIndex,
    }
  }

  let nextDefault = 0
  const preferred = candidates[defaultSelectedIndex]
  if (preferred) {
    const idx = filtered.findIndex(
      (c) =>
        c.start_frame === preferred.start_frame && c.end_frame === preferred.end_frame,
    )
    if (idx >= 0) nextDefault = idx
    else {
      const formal = filtered.findIndex((c) => !c.is_practice)
      nextDefault = formal >= 0 ? formal : 0
    }
  } else {
    const formal = filtered.findIndex((c) => !c.is_practice)
    nextDefault = formal >= 0 ? formal : 0
  }

  return {
    swing_candidates: filtered,
    default_selected_index: nextDefault,
  }
}
