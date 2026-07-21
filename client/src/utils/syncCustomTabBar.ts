/**
 * 自定义 tabBar 选中态同步（原生 getTabBar + setSelected）。
 */

import Taro from '@tarojs/taro'
import type { AppRole } from '@/utils/tabBarRole'

type CustomTabBarInstance = {
  setSelected?: (index: number) => void
  setRole?: (role: AppRole) => void
}

function getActiveCustomTabBar(): CustomTabBarInstance | null {
  if (process.env.TARO_ENV !== 'weapp') return null
  try {
    const page = Taro.getCurrentInstance().page as unknown
    if (!page || typeof Taro.getTabBar !== 'function') return null
    return (Taro.getTabBar(page) as CustomTabBarInstance | null) ?? null
  } catch {
    return null
  }
}

/** 各 tab 页 useDidShow 里调用，避免切页后高亮错位。 */
export function syncCustomTabBarSelected(index: number): void {
  getActiveCustomTabBar()?.setSelected?.(index)
}

/** 身份切换时更新自定义 tab 文案（工作台/学员等）。 */
export function syncCustomTabBarRole(role: AppRole): boolean {
  const bar = getActiveCustomTabBar()
  if (!bar?.setRole) return false
  bar.setRole(role)
  return true
}
