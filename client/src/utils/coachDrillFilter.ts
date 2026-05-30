/**
 * M8-05 · 教练布置作业时的 drill 类目筛选。
 */

import { DRILL_CATALOG, type DrillDetail } from '@/constants/drillLibrary'

export type CoachDrillCategory = 'all' | 'full_swing' | 'putting' | 'chipping'

export const COACH_DRILL_CATEGORY_LABEL: Record<CoachDrillCategory, string> = {
  all: '全部',
  full_swing: '全挥杆',
  putting: '推杆',
  chipping: '切杆',
}

export function filterDrillsByCategory(
  category: CoachDrillCategory,
  catalog: readonly DrillDetail[] = DRILL_CATALOG,
): DrillDetail[] {
  if (category === 'all') return [...catalog]
  return catalog.filter((d) => (d.category || 'full_swing') === category)
}

export function findDrillIndexInList(
  drills: readonly DrillDetail[],
  drillId: string | undefined,
): number {
  if (!drillId) return 0
  const idx = drills.findIndex((d) => d.drill_id === drillId)
  return idx >= 0 ? idx : 0
}
