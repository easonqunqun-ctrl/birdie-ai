import { FC } from 'react'
import { View, Text, Button } from '@tarojs/components'
import Taro, { useDidShow } from '@tarojs/taro'
import { useUserStore } from '@/store/userStore'
import { FREQ_LABEL, GOAL_LABEL, LEVEL_LABEL } from '@/constants/golf'
import type { GolfLevel, PrimaryGoal, WeeklyFreq } from '@/types/api'
import './index.scss'

const ProfilePage: FC = () => {
  const { user, token, logout, fetchMe } = useUserStore()

  // 从"编辑档案"返回时自动刷新，保证卡片展示是最新的。
  useDidShow(() => {
    if (token) fetchMe().catch(() => undefined)
  })

  if (!user) {
    return (
      <View className='profile profile--empty'>
        <Text>请先登录</Text>
      </View>
    )
  }

  const handleLogout = () => {
    Taro.showModal({
      title: '提示',
      content: '确认退出登录？',
      success: ({ confirm }) => {
        if (confirm) {
          logout()
          Taro.reLaunch({ url: '/pages/login/index' })
        }
      }
    })
  }

  const handleEdit = () => {
    Taro.navigateTo({ url: '/pages/profile/edit' })
  }

  const isMember = user.membership_type !== 'free'
  const membershipLabel = isMember ? '会员' : '免费用户'

  const levelText = user.golf_level ? LEVEL_LABEL[user.golf_level as GolfLevel] : '未设置'
  const goalsText = user.primary_goals.length > 0
    ? user.primary_goals
        .map((g) => GOAL_LABEL[g as PrimaryGoal] ?? g)
        .join(' · ')
    : '未设置'
  const freqText = user.weekly_practice_frequency
    ? FREQ_LABEL[user.weekly_practice_frequency as WeeklyFreq]
    : '未设置'

  return (
    <View className='profile'>
      <View className='profile__card'>
        <View className='profile__avatar'>
          <Text>{(user.nickname || '球友')[0]}</Text>
        </View>
        <View className='profile__card-info'>
          <Text className='profile__nickname'>{user.nickname || '球友'}</Text>
          <Text
            className={`profile__badge ${isMember ? 'profile__badge--member' : 'profile__badge--free'}`}
          >
            {membershipLabel}
          </Text>
        </View>
        <Text className='profile__edit' onClick={handleEdit}>
          编辑
        </Text>
      </View>

      {user.stats && (
        <View className='profile__stats'>
          <View className='profile__stat'>
            <Text className='profile__stat-value'>{user.stats.total_analyses}</Text>
            <Text className='profile__stat-label'>分析次数</Text>
          </View>
          <View className='profile__stat'>
            <Text className='profile__stat-value'>{user.stats.streak_days}</Text>
            <Text className='profile__stat-label'>连续打卡</Text>
          </View>
          <View className='profile__stat'>
            <Text className='profile__stat-value'>{user.stats.best_score}</Text>
            <Text className='profile__stat-label'>最高分</Text>
          </View>
        </View>
      )}

      <View className='profile__section'>
        <View className='profile__section-header'>
          <Text className='profile__section-title'>高尔夫档案</Text>
          <Text className='profile__section-action' onClick={handleEdit}>
            修改
          </Text>
        </View>
        <View className='profile__rows'>
          <View className='profile__row'>
            <Text className='profile__row-label'>水平</Text>
            <Text className='profile__row-value'>{levelText}</Text>
          </View>
          <View className='profile__row'>
            <Text className='profile__row-label'>目标</Text>
            <Text className='profile__row-value'>{goalsText}</Text>
          </View>
          <View className='profile__row'>
            <Text className='profile__row-label'>练习频率</Text>
            <Text className='profile__row-value'>{freqText}</Text>
          </View>
        </View>
      </View>

      <View className='profile__section'>
        <View className='profile__menu'>
          <View
            className='profile__menu-item'
            onClick={() => Taro.navigateTo({ url: '/pages/analysis/history' })}
          >
            <Text className='profile__menu-icon'>📋</Text>
            <Text className='profile__menu-label'>我的分析报告</Text>
            <Text className='profile__menu-arrow'>›</Text>
          </View>
          <View
            className='profile__menu-item'
            onClick={() => Taro.navigateTo({ url: '/pages/coach/index' })}
          >
            <Text className='profile__menu-icon'>💬</Text>
            <Text className='profile__menu-label'>AI 教练对话</Text>
            <Text className='profile__menu-arrow'>›</Text>
          </View>
          <View
            className='profile__menu-item'
            onClick={() =>
              Taro.showToast({ title: '对话历史 W7 再开放', icon: 'none' })
            }
          >
            <Text className='profile__menu-icon'>🗂️</Text>
            <Text className='profile__menu-label'>对话历史</Text>
            <Text className='profile__menu-arrow'>›</Text>
          </View>
        </View>
      </View>

      <View className='profile__actions'>
        <Button className='profile__btn profile__btn--ghost' onClick={handleLogout}>
          退出登录
        </Button>
      </View>
    </View>
  )
}

export default ProfilePage
