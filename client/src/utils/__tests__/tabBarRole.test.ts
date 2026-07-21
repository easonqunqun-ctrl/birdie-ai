import Taro from '@tarojs/taro'
import { applyTabBarRole } from '@/utils/tabBarRole'
import { syncCustomTabBarRole } from '@/utils/syncCustomTabBar'

jest.mock('@/utils/syncCustomTabBar', () => ({
  syncCustomTabBarRole: jest.fn(() => false),
  syncCustomTabBarSelected: jest.fn(),
}))

describe('applyTabBarRole', () => {
  const setTabBarItem = Taro.setTabBarItem as jest.Mock
  const syncRole = syncCustomTabBarRole as jest.Mock

  beforeEach(() => {
    setTabBarItem.mockClear()
    syncRole.mockClear()
    syncRole.mockReturnValue(false)
    process.env.TARO_ENV = 'weapp'
  })

  test('user → 球友 Tab 文案', () => {
    applyTabBarRole('user')
    expect(setTabBarItem).toHaveBeenCalledTimes(4)
    expect(setTabBarItem).toHaveBeenNthCalledWith(1, { index: 0, text: '首页' })
    expect(setTabBarItem).toHaveBeenNthCalledWith(2, { index: 1, text: 'AI 教练' })
    expect(setTabBarItem).toHaveBeenNthCalledWith(3, { index: 2, text: '训练' })
    expect(setTabBarItem).toHaveBeenNthCalledWith(4, { index: 3, text: '我的' })
  })

  test('coach → 教练 Tab 文案', () => {
    applyTabBarRole('coach')
    expect(setTabBarItem).toHaveBeenCalledTimes(4)
    expect(setTabBarItem).toHaveBeenNthCalledWith(1, { index: 0, text: '工作台' })
    expect(setTabBarItem).toHaveBeenNthCalledWith(2, { index: 1, text: 'AI 教练' })
    expect(setTabBarItem).toHaveBeenNthCalledWith(3, { index: 2, text: '学员' })
    expect(setTabBarItem).toHaveBeenNthCalledWith(4, { index: 3, text: '我的' })
  })

  test('自定义 tabBar 已挂载 → setRole，不再调 setTabBarItem', () => {
    syncRole.mockReturnValue(true)
    applyTabBarRole('coach')
    expect(syncRole).toHaveBeenCalledWith('coach')
    expect(setTabBarItem).not.toHaveBeenCalled()
  })

  test('RN 环境 no-op', () => {
    process.env.TARO_ENV = 'rn'
    applyTabBarRole('coach')
    expect(setTabBarItem).not.toHaveBeenCalled()
    expect(syncRole).not.toHaveBeenCalled()
  })
})
