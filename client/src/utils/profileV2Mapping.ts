/**
 * P2-M9-03 · 画像 2.0 与 v1 用户档案字段映射（onboarding 双写用）
 */

import type { GolfLevel, PrimaryGoal, WeeklyFreq } from '@/types/api'
import { GOAL_LABEL, GOALS } from '@/constants/golf'
import { HANDICAP_RANGES } from '@/constants/profileV2'

export function mapHandicapSelfToGolfLevel(handicapSelf: number): GolfLevel {
  if (handicapSelf <= 10) return 'advanced'
  if (handicapSelf <= 18) return 'intermediate'
  if (handicapSelf <= 25) return 'intermediate'
  if (handicapSelf <= 36) return 'elementary'
  return 'beginner'
}

export function mapWeeklySessionsToFreq(sessions: number): WeeklyFreq {
  if (sessions <= 0) return 'occasional'
  if (sessions === 1) return 'once'
  if (sessions <= 3) return 'frequent'
  return 'daily'
}

export function handicapRangeIdFromSelf(handicapSelf: number | null): string | null {
  if (handicapSelf == null) return null
  let best = HANDICAP_RANGES[0]
  let bestDiff = Math.abs(best.value - handicapSelf)
  for (const r of HANDICAP_RANGES) {
    const diff = Math.abs(r.value - handicapSelf)
    if (diff < bestDiff) {
      best = r
      bestDiff = diff
    }
  }
  return best.id
}

export function goalsFromMidLongLabels(labels: string[]): PrimaryGoal[] {
  const set = new Set(labels)
  return GOALS.filter((g) => set.has(GOAL_LABEL[g.value])).map((g) => g.value)
}
