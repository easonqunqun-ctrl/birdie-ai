import { FC, useEffect, useState } from 'react'
import { View, Text, Button, Switch } from '@tarojs/components'
import Taro, { useDidShow } from '@tarojs/taro'
import EnvBadge from '@/components/EnvBadge'
import { useUserStore } from '@/store/userStore'
import { switchToCoach, toastTabNavigationFailure } from '@/utils/tabNav'
import { FREQ_LABEL, GOAL_LABEL, LEVEL_LABEL } from '@/constants/golf'
import {
  PAYMENT_ENABLED_FLAG,
  PHASE2_COACH_ENABLED_FLAG,
  PHASE2_COURSES_ENABLED_FLAG,
  PHASE2_MEETUP_ENABLED_FLAG,
  PHASE2_PROFILE_V2_ENABLED_FLAG,
  PHASE2_PROS_ENABLED_FLAG,
  PHASE2_YARDAGE_BOOK_ENABLED_FLAG,
} from '@/constants/flags'
import type { GolfLevel, PrimaryGoal, WeeklyFreq } from '@/types/api'
import { coachStudentsService } from '@/services/coachStudentsService'
import './index.scss'

const ProfilePage: FC = () => {
  const { user, token, initialized, logout, fetchMe, bootstrap, currentRole, setRole } =
    useUserStore()
  const [roleSwitchSaving, setRoleSwitchSaving] = useState(false)
  const [pendingCoachInvites, setPendingCoachInvites] = useState(0)

  useEffect(() => {
    if (!initialized) {
      void bootstrap()
    }
  }, [initialized, bootstrap])

  // 从"编辑档案"返回时自动刷新，保证卡片展示是最新的。
  useDidShow(() => {
    if (token) fetchMe().catch(() => undefined)
    if (token && PHASE2_COACH_ENABLED_FLAG) {
      coachStudentsService
        .myCoachOverview()
        .then((data) => setPendingCoachInvites(data.pending.length))
        .catch(() => setPendingCoachInvites(0))
    }
  })

  if (!initialized) {
    return (
      <View className='profile profile--empty'>
        <Text>加载中...</Text>
      </View>
    )
  }

  if (!token) {
    const goLogin = () => {
      Taro.navigateTo({ url: '/pages/login/index' })
    }
    return (
      <View className='profile profile--empty'>
        <EnvBadge />
        <Text className='profile__guest-hint'>请先登录以查看账号、分析与设置</Text>
        <Button className='profile__guest-login' type='primary' onClick={goLogin}>
          去登录
        </Button>
      </View>
    )
  }

  if (!user) {
    return (
      <View className='profile profile--empty'>
        <Text>加载中...</Text>
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

  const onCoachModeChange = async (checked: boolean) => {
    if (roleSwitchSaving) return
    const targetRole = checked ? 'coach' : 'user'
    if (targetRole === currentRole) return
    setRoleSwitchSaving(true)
    try {
      await setRole(targetRole)
      Taro.showToast({
        title: checked ? '已切换教练模式' : '已切换球友模式',
        icon: 'none',
      })
    } catch (e) {
      Taro.showToast({
        title: e instanceof Error ? e.message : '切换失败',
        icon: 'none',
      })
    } finally {
      setRoleSwitchSaving(false)
    }
  }

  const isMember = user.is_member
  const membershipLabel = isMember
    ? `${user.membership_type === 'yearly' ? '年度' : '月度'}会员 · ${user.membership_days_remaining}天`
    : '免费用户'

  const levelText = user.golf_level ? LEVEL_LABEL[user.golf_level as GolfLevel] : '未设置'
  const goalsText = user.primary_goals.length > 0
    ? user.primary_goals
        .map((g) => GOAL_LABEL[g as PrimaryGoal] ?? g)
        .join(' · ')
    : '未设置'
  const freqText = user.weekly_practice_frequency
    ? FREQ_LABEL[user.weekly_practice_frequency as WeeklyFreq]
    : '未设置'

  const delAt = user.account_deletion_scheduled_at

  return (
    <View className='profile'>
      <EnvBadge />
      {delAt && (
        <View
          className='profile__del-banner'
          onClick={() => Taro.navigateTo({ url: '/pages/profile/account-deletion' })}
        >
          <Text className='profile__del-banner-text'>
            账号已排期注销，点此查看或撤销
          </Text>
        </View>
      )}
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

      {PHASE2_COACH_ENABLED_FLAG && user.is_active_coach && (
        <View className='profile__section profile__role-switch'>
          <View className='profile__role-switch-row'>
            <View className='profile__role-switch-text'>
              <Text className='profile__role-switch-title'>教练模式</Text>
              <Text className='profile__role-switch-desc'>
                开启后 TabBar 切换为教练工作台，可访问学员与教练工具
              </Text>
            </View>
            <Switch
              checked={currentRole === 'coach'}
              disabled={roleSwitchSaving}
              color='var(--color-primary)'
              onChange={(e) => void onCoachModeChange(Boolean(e.detail.value))}
            />
          </View>
        </View>
      )}

      {PHASE2_COACH_ENABLED_FLAG && pendingCoachInvites > 0 && (
        <View
          className='profile__coach-banner'
          onClick={() => Taro.navigateTo({ url: '/pages/coach-invite/index' })}
        >
          <Text className='profile__coach-banner-text'>
            你有 {pendingCoachInvites} 条教练邀请待处理
          </Text>
          <Text className='profile__coach-banner-action'>去处理 ›</Text>
        </View>
      )}

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
          {/*
            P2-M9-02：装备清单入口；与 backend PHASE2_PROFILE_V2_ENABLED 双端联动，
            未启用时隐藏。W22 灰度时一起翻 flag。
          */}
          {PHASE2_PROFILE_V2_ENABLED_FLAG && (
            <View
              className='profile__menu-item'
              onClick={() => Taro.navigateTo({ url: '/pages/profile/clubs' })}
            >
              <Text className='profile__menu-icon'>🏌️</Text>
              <Text className='profile__menu-label'>我的装备</Text>
              <Text className='profile__menu-arrow'>›</Text>
            </View>
          )}
          {PHASE2_YARDAGE_BOOK_ENABLED_FLAG && PHASE2_PROFILE_V2_ENABLED_FLAG && (
            <View
              className='profile__menu-item'
              onClick={() => Taro.navigateTo({ url: '/pages/profile/yardage-book/index' })}
            >
              <Text className='profile__menu-icon'>📏</Text>
              <Text className='profile__menu-label'>个人 yardage book</Text>
              <Text className='profile__menu-arrow'>›</Text>
            </View>
          )}
          {PHASE2_PROFILE_V2_ENABLED_FLAG && (
            <View
              className='profile__menu-item'
              onClick={() => Taro.navigateTo({ url: '/pages/profile/favorite-venues' })}
            >
              <Text className='profile__menu-icon'>📍</Text>
              <Text className='profile__menu-label'>常去球馆</Text>
              <Text className='profile__menu-arrow'>›</Text>
            </View>
          )}
          {PHASE2_PROFILE_V2_ENABLED_FLAG && (
            <View
              className='profile__menu-item'
              onClick={() => Taro.navigateTo({ url: '/pages/profile/profile-v2' })}
            >
              <Text className='profile__menu-icon'>🧭</Text>
              <Text className='profile__menu-label'>我的画像</Text>
              <Text className='profile__menu-arrow'>›</Text>
            </View>
          )}
          {/*
            P2-M11-03：课程学习路径入口；与 backend PHASE2_COURSES_ENABLED 同步。
          */}
          {PHASE2_COURSES_ENABLED_FLAG && (
            <View
              className='profile__menu-item'
              onClick={() => Taro.navigateTo({ url: '/pages/courses/index' })}
            >
              <Text className='profile__menu-icon'>📚</Text>
              <Text className='profile__menu-label'>学习路径</Text>
              <Text className='profile__menu-arrow'>›</Text>
            </View>
          )}
          {/*
            P2-M12-03：球手对比库入口；与 backend PHASE2_PROS_ENABLED 同步。
          */}
          {PHASE2_PROS_ENABLED_FLAG && (
            <View
              className='profile__menu-item'
              onClick={() => Taro.navigateTo({ url: '/pages/pros/index' })}
            >
              <Text className='profile__menu-icon'>⛳</Text>
              <Text className='profile__menu-label'>球手对比库</Text>
              <Text className='profile__menu-arrow'>›</Text>
            </View>
          )}
          {/*
            P2-M13：约球邀请列表入口；与 backend PHASE2_MEETUP_ENABLED 同步。
            预留入口；M13 客户端列表 / 详情页由后续 PR 引入，本 PR 仅挂入口
            （未启用时隐藏，故不会出现"点击 404"的尴尬）。
          */}
          {PHASE2_MEETUP_ENABLED_FLAG && (
            <View
              className='profile__menu-item'
              onClick={() => Taro.navigateTo({ url: '/pages/meetup/index' })}
            >
              <Text className='profile__menu-icon'>🤝</Text>
              <Text className='profile__menu-label'>约球邀请</Text>
              <Text className='profile__menu-arrow'>›</Text>
            </View>
          )}

          {PHASE2_COACH_ENABLED_FLAG && !user?.is_active_coach && (
            <View
              className='profile__menu-item'
              onClick={() => Taro.navigateTo({ url: '/pages/coach/apply' })}
            >
              <Text className='profile__menu-icon'>🎓</Text>
              <Text className='profile__menu-label'>申请成为教练</Text>
              <Text className='profile__menu-arrow'>›</Text>
            </View>
          )}
          {PHASE2_COACH_ENABLED_FLAG && user?.is_active_coach && currentRole === 'coach' && (
            <View
              className='profile__menu-item'
              onClick={() => Taro.navigateTo({ url: '/pages/coach/students/index' })}
            >
              <Text className='profile__menu-icon'>👥</Text>
              <Text className='profile__menu-label'>我的学员</Text>
              <Text className='profile__menu-arrow'>›</Text>
            </View>
          )}
          {PHASE2_COACH_ENABLED_FLAG && user?.is_active_coach && currentRole === 'coach' && (
            <View
              className='profile__menu-item'
              onClick={() => Taro.navigateTo({ url: '/pages/coach/session-recap/index' })}
            >
              <Text className='profile__menu-icon'>📄</Text>
              <Text className='profile__menu-label'>教学报告</Text>
              <Text className='profile__menu-arrow'>›</Text>
            </View>
          )}
          {PHASE2_COACH_ENABLED_FLAG && user?.is_active_coach && currentRole === 'coach' && (
            <View
              className='profile__menu-item'
              onClick={() => Taro.navigateTo({ url: '/pages/coach/students-invite' })}
            >
              <Text className='profile__menu-icon'>🧑‍🎓</Text>
              <Text className='profile__menu-label'>邀请学员</Text>
              <Text className='profile__menu-arrow'>›</Text>
            </View>
          )}
          {PHASE2_COACH_ENABLED_FLAG && (
            <View
              className='profile__menu-item'
              onClick={() => Taro.navigateTo({ url: '/pages/coach-invite/index' })}
            >
              <Text className='profile__menu-icon'>📩</Text>
              <Text className='profile__menu-label'>教练邀请</Text>
              <Text className='profile__menu-arrow'>›</Text>
            </View>
          )}
          {PHASE2_COACH_ENABLED_FLAG && (
            <View
              className='profile__menu-item'
              onClick={() => Taro.navigateTo({ url: '/pages/profile/coach-visibility' })}
            >
              <Text className='profile__menu-icon'>🔒</Text>
              <Text className='profile__menu-label'>教练可见字段</Text>
              <Text className='profile__menu-arrow'>›</Text>
            </View>
          )}
          <View
            className='profile__menu-item'
            onClick={() => void switchToCoach().catch(toastTabNavigationFailure)}
          >
            <Text className='profile__menu-icon'>💬</Text>
            <Text className='profile__menu-label'>AI 教练对话</Text>
            <Text className='profile__menu-arrow'>›</Text>
          </View>
          {/*
            W8-T3：会员中心入口 PAYMENT_ENABLED 门控。
              - false（W8 内测）：隐藏整行，避免普通用户看到"开通"链路
              - true（W9 正式）：恢复正常入口
            页面 `pages/profile/membership` 本身不删（管理员仍可手动 navigateTo 走 mock-pay）
          */}
          {PAYMENT_ENABLED_FLAG && (
            <View
              className='profile__menu-item'
              onClick={() => Taro.navigateTo({ url: '/pages/profile/membership' })}
            >
              <Text className='profile__menu-icon'>👑</Text>
              <Text className='profile__menu-label'>会员中心</Text>
              <Text className='profile__menu-arrow'>›</Text>
            </View>
          )}
          <View
            className='profile__menu-item'
            onClick={() => Taro.navigateTo({ url: '/pages/profile/invitations' })}
          >
            <Text className='profile__menu-icon'>🎁</Text>
            <Text className='profile__menu-label'>邀请好友</Text>
            <Text className='profile__menu-arrow'>›</Text>
          </View>
          <View
            className='profile__menu-item'
            onClick={() =>
              Taro.navigateTo({ url: '/pages/profile/chat-history' })
            }
          >
            <Text className='profile__menu-icon'>🗂️</Text>
            <Text className='profile__menu-label'>对话历史</Text>
            <Text className='profile__menu-arrow'>›</Text>
          </View>
          <View
            className='profile__menu-item'
            onClick={() => Taro.navigateTo({ url: '/pages/profile/feedback' })}
          >
            <Text className='profile__menu-icon'>📮</Text>
            <Text className='profile__menu-label'>意见反馈</Text>
            <Text className='profile__menu-arrow'>›</Text>
          </View>
          <View
            className='profile__menu-item'
            onClick={() => Taro.navigateTo({ url: '/pages/profile/settings' })}
          >
            <Text className='profile__menu-icon'>⚙️</Text>
            <Text className='profile__menu-label'>设置</Text>
            <Text className='profile__menu-arrow'>›</Text>
          </View>
          <View
            className='profile__menu-item'
            onClick={() => Taro.navigateTo({ url: '/pages/profile/about' })}
          >
            <Text className='profile__menu-icon'>ℹ️</Text>
            <Text className='profile__menu-label'>关于领翼golf</Text>
            <Text className='profile__menu-arrow'>›</Text>
          </View>
          <View
            className='profile__menu-item'
            onClick={() =>
              Taro.navigateTo({ url: '/pages/profile/account-deletion' })
            }
          >
            <Text className='profile__menu-icon'>⚠️</Text>
            <Text className='profile__menu-label'>注销账号</Text>
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
