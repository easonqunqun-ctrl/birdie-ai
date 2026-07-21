/**
 * 自定义 tabBar：可放大文字与图标（原生 tabBar 不支持 fontSize）。
 * 各 tab 页 useDidShow 里调 syncCustomTabBarSelected(index)。
 */
import { Component } from 'react'
import { View, Text, Image } from '@tarojs/components'
import Taro from '@tarojs/taro'
import type { AppRole } from '@/utils/tabBarRole'
import './index.scss'

const USER_LABELS = ['首页', 'AI 教练', '训练', '我的'] as const
const COACH_LABELS = ['工作台', 'AI 教练', '学员', '我的'] as const

type TabItem = {
  pagePath: string
  text: string
  iconPath: string
  selectedIconPath: string
}

type State = {
  selected: number
  role: AppRole
  list: TabItem[]
}

function buildList(role: AppRole): TabItem[] {
  const labels = role === 'coach' ? COACH_LABELS : USER_LABELS
  return [
    {
      pagePath: '/pages/index/index',
      text: labels[0],
      iconPath: '../assets/tab/home.png',
      selectedIconPath: '../assets/tab/home_active.png',
    },
    {
      pagePath: '/pages/coach/index',
      text: labels[1],
      iconPath: '../assets/tab/coach.png',
      selectedIconPath: '../assets/tab/coach_active.png',
    },
    {
      pagePath: '/pages/training/index',
      text: labels[2],
      iconPath: '../assets/tab/training.png',
      selectedIconPath: '../assets/tab/training_active.png',
    },
    {
      pagePath: '/pages/profile/index',
      text: labels[3],
      iconPath: '../assets/tab/profile.png',
      selectedIconPath: '../assets/tab/profile_active.png',
    },
  ]
}

export default class CustomTabBar extends Component<object, State> {
  state: State = {
    selected: 0,
    role: 'user',
    list: buildList('user'),
  }

  /** 供各 tab 页 getTabBar().setSelected(i) 调用 */
  setSelected(index: number) {
    this.setState({ selected: index })
  }

  /** 供 applyTabBarRole → getTabBar().setRole(role) */
  setRole(role: AppRole) {
    this.setState({ role, list: buildList(role) })
  }

  private switchTab = (index: number, url: string) => {
    this.setSelected(index)
    void Taro.switchTab({ url })
  }

  render() {
    const { list, selected } = this.state
    return (
      <View className='custom-tab-bar'>
        {list.map((item, index) => {
          const active = selected === index
          return (
            <View
              key={item.pagePath}
              className={`custom-tab-bar__item${active ? ' custom-tab-bar__item--active' : ''}`}
              onClick={() => this.switchTab(index, item.pagePath)}
            >
              <Image
                className='custom-tab-bar__icon'
                src={active ? item.selectedIconPath : item.iconPath}
                mode='aspectFit'
              />
              <Text
                className={`custom-tab-bar__text${active ? ' custom-tab-bar__text--active' : ''}`}
              >
                {item.text}
              </Text>
            </View>
          )
        })}
      </View>
    )
  }
}
