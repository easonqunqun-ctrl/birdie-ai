import {
  mapHandicapSelfToGolfLevel,
  mapWeeklySessionsToFreq,
  handicapRangeIdFromSelf,
  goalsFromMidLongLabels,
} from '@/utils/profileV2Mapping'
import { GOAL_LABEL } from '@/constants/golf'

describe('profileV2Mapping', () => {
  test('mapHandicapSelfToGolfLevel', () => {
    expect(mapHandicapSelfToGolfLevel(8)).toBe('advanced')
    expect(mapHandicapSelfToGolfLevel(14)).toBe('intermediate')
    expect(mapHandicapSelfToGolfLevel(30)).toBe('elementary')
    expect(mapHandicapSelfToGolfLevel(40)).toBe('beginner')
  })

  test('mapWeeklySessionsToFreq', () => {
    expect(mapWeeklySessionsToFreq(0)).toBe('occasional')
    expect(mapWeeklySessionsToFreq(1)).toBe('once')
    expect(mapWeeklySessionsToFreq(2)).toBe('frequent')
    expect(mapWeeklySessionsToFreq(5)).toBe('daily')
  })

  test('handicapRangeIdFromSelf picks nearest band', () => {
    expect(handicapRangeIdFromSelf(14)).toBe('10_18')
    expect(handicapRangeIdFromSelf(null)).toBeNull()
  })

  test('goalsFromMidLongLabels', () => {
    const goals = goalsFromMidLongLabels([GOAL_LABEL.distance, '未知目标'])
    expect(goals).toEqual(['distance'])
  })
})
