/**
 * M8-02 · TabBar 文案随 user/coach 身份切换。
 */

import Taro from '@tarojs/taro'
import { syncCustomTabBarRole } from '@/utils/syncCustomTabBar'

export type AppRole = 'user' | 'coach'

const USER_TAB_LABELS = ['首页', 'AI 教练', '训练', '我的'] as const
const COACH_TAB_LABELS = ['工作台', 'AI 教练', '学员', '我的'] as const

export function applyTabBarRole(role: AppRole): void {
  if (process.env.TARO_ENV !== 'weapp' && process.env.TARO_ENV !== 'h5') {
    return
  }
  // 自定义 tabBar：走组件 setRole；失败再 fallback 原生 setTabBarItem（H5 / 未挂载时）
  if (process.env.TARO_ENV === 'weapp' && syncCustomTabBarRole(role)) {
    return
  }
  const labels = role === 'coach' ? COACH_TAB_LABELS : USER_TAB_LABELS
  labels.forEach((text, index) => {
    void Taro.setTabBarItem({ index, text }).catch(() => undefined)
  })
}
