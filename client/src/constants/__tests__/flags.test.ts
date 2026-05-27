/**
 * P2-M9-02 entry mount · flags 出口契约测试。
 *
 * 目的
 * ----
 * 1. 确保所有 P2 灰度 flag 都是 boolean 类型（避免误写成 string/undefined 导致
 *    profile 页 falsy 但不为 false 时入口随机出现）
 * 2. 上线前防止有人把默认值改成 true 而忘了同步后端 settings
 *    （生产 P2 默认 false；运营手动 release 时再翻）
 */

import {
  PAYMENT_ENABLED_FLAG,
  PHASE2_COURSES_ENABLED_FLAG,
  PHASE2_MEETUP_ENABLED_FLAG,
  PHASE2_PROFILE_V2_ENABLED_FLAG,
  PHASE2_PROS_ENABLED_FLAG,
} from '@/constants/flags'

describe('feature flags', () => {
  test('PHASE2_* flags are strict booleans', () => {
    for (const f of [
      PHASE2_PROFILE_V2_ENABLED_FLAG,
      PHASE2_COURSES_ENABLED_FLAG,
      PHASE2_PROS_ENABLED_FLAG,
      PHASE2_MEETUP_ENABLED_FLAG,
    ]) {
      expect(typeof f).toBe('boolean')
    }
  })

  test('PHASE2_* defaults are false in source (运营手动开启)', () => {
    // 这是「不要不小心 ship 灰度功能」的硬门禁；
    // 想正式翻 flag 时，把默认值改成 true 后再删除本断言。
    expect(PHASE2_PROFILE_V2_ENABLED_FLAG).toBe(false)
    expect(PHASE2_COURSES_ENABLED_FLAG).toBe(false)
    expect(PHASE2_PROS_ENABLED_FLAG).toBe(false)
    expect(PHASE2_MEETUP_ENABLED_FLAG).toBe(false)
  })

  test('PAYMENT_ENABLED_FLAG is a boolean (编译期常量)', () => {
    expect(typeof PAYMENT_ENABLED_FLAG).toBe('boolean')
  })
})
