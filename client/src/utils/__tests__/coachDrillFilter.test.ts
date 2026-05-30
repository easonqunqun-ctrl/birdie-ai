import {
  COACH_DRILL_CATEGORY_LABEL,
  filterDrillsByCategory,
  findDrillIndexInList,
} from '@/utils/coachDrillFilter'

describe('coachDrillFilter', () => {
  test('filterDrillsByCategory putting', () => {
    const putting = filterDrillsByCategory('putting')
    expect(putting.length).toBeGreaterThan(0)
    expect(putting.every((d) => d.category === 'putting')).toBe(true)
  })

  test('filterDrillsByCategory all returns full catalog', () => {
    const all = filterDrillsByCategory('all')
    const putting = filterDrillsByCategory('putting')
    expect(all.length).toBeGreaterThan(putting.length)
  })

  test('findDrillIndexInList', () => {
    const drills = filterDrillsByCategory('putting')
    const idx = findDrillIndexInList(drills, drills[0]?.drill_id)
    expect(idx).toBe(0)
    expect(findDrillIndexInList(drills, 'missing_id')).toBe(0)
  })

  test('category labels cover tabs', () => {
    expect(COACH_DRILL_CATEGORY_LABEL.putting).toBe('推杆')
    expect(COACH_DRILL_CATEGORY_LABEL.chipping).toBe('切杆')
  })
})
