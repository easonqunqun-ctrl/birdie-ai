import { FC, useEffect, useState } from 'react'
import { View, Text, Button } from '@tarojs/components'
import Taro from '@tarojs/taro'
import { useShareAppMessage, useShareTimeline } from '@/adapters/share'
import {
  invitationService,
  type InvitationItem,
  type InviteInfo
} from '@/services/invitationService'
import { describePageLoadFailure } from '@/services/request'
import { BRAND_SHARE_COVER } from '@/constants/brandAssets'
import {
  groupInvitationsByRewardTier,
  INVITE_REWARD_DAYS_PER_TIER,
} from '@/utils/invitationRewardTiers'
import './invitations.scss'

/**
 * W7-T4 邀请好友页.
 *
 * 顶部：邀请码 + 复制；进度条（已有效 / 下一档奖励需求 / 已累计奖励天数）
 * 中部：规则说明
 * 底部：邀请记录列表（被邀请者脱敏昵称 + 状态）
 *
 * 分享（onShareAppMessage）把 invite_code 带到 path 上，被分享用户点击
 * 唤起小程序，走 login 时把 code 回传给后端（W7-T5 会把该链路打通）。
 */
const InvitationsPage: FC = () => {
  const [info, setInfo] = useState<InviteInfo | null>(null)
  const [list, setList] = useState<InvitationItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      const [i, l] = await Promise.all([
        invitationService.getInfo(),
        invitationService.listInvitations()
      ])
      setInfo(i)
      setList(l)
    } catch (e) {
      setError(describePageLoadFailure(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  useShareAppMessage(() => {
    const code = info?.invite_code ?? ''
    return {
      title: '用领翼golf 看你挥杆哪里不对，我们一起进步',
      path: `/pages/login/index?invite_code=${code}`,
      imageUrl: BRAND_SHARE_COVER
    }
  })

  useShareTimeline(() => ({
    title: '领翼golf · 邀请球友一起练挥杆',
    query: info?.invite_code ? `invite_code=${info.invite_code}` : '',
    imageUrl: BRAND_SHARE_COVER,
  }))

  const handleCopy = () => {
    if (!info?.invite_code) return
    Taro.setClipboardData({
      data: info.invite_code,
      success: () => Taro.showToast({ title: '邀请码已复制', icon: 'success' })
    })
  }

  const handleShare = () => {
    Taro.showToast({ title: '点击右上角 · 分享给朋友', icon: 'none' })
  }

  if (loading) {
    return (
      <View className='invitations invitations--loading'>
        <Text>加载中...</Text>
      </View>
    )
  }

  if (error || !info) {
    return (
      <View className='invitations invitations--error'>
        <Text>{error || '数据异常'}</Text>
        <Button className='invitations__retry' onClick={load}>
          重试
        </Button>
      </View>
    )
  }

  const progressPct = Math.min(
    100,
    Math.round(
      (info.valid_count / Math.max(info.next_reward_at, 1)) * 100
    )
  )

  const inviteSections = groupInvitationsByRewardTier(list)

  return (
    <View className='invitations'>
      <View className='invitations__hero'>
        <Text className='invitations__hero-title'>我的邀请码</Text>
        <Text className='invitations__code'>{info.invite_code}</Text>
        <View className='invitations__hero-actions'>
          <Button className='invitations__btn invitations__btn--primary' onClick={handleShare}>
            分享给朋友
          </Button>
          <Button className='invitations__btn invitations__btn--ghost' onClick={handleCopy}>
            复制邀请码
          </Button>
        </View>
      </View>

      <View className='invitations__progress-card'>
        <View className='invitations__progress-top'>
          <Text className='invitations__progress-label'>
            有效邀请：{info.valid_count} / {info.next_reward_at}
          </Text>
          <Text className='invitations__progress-hint'>
            {info.days_to_next_reward > 0
              ? `再邀请 ${info.days_to_next_reward} 位好友并完成首次分析，得 7 天会员`
              : '已达成本档奖励 🎉'}
          </Text>
        </View>
        <View className='invitations__progress-bar'>
          <View
            className='invitations__progress-fill'
            style={{ width: `${progressPct}%` }}
          />
        </View>
        <Text className='invitations__progress-bonus'>
          已累计获得会员奖励：{info.total_bonus_days} 天
        </Text>
      </View>

      <View className='invitations__rules'>
        <Text className='invitations__rules-title'>邀请规则</Text>
        <Text className='invitations__rules-item'>
          · 好友用你的邀请码登录后，你和 TA 当月各 +1 次分析
        </Text>
        <Text className='invitations__rules-item'>
          · 好友完成首次挥杆分析 → 计为「有效邀请」
        </Text>
        <Text className='invitations__rules-item'>
          · 每累计 5 位有效邀请，赠 7 天会员（叠加到现有会员有效期）
        </Text>
      </View>

      <View className='invitations__list'>
        <Text className='invitations__list-title'>奖励分档（每 5 人 +{INVITE_REWARD_DAYS_PER_TIER} 天会员）</Text>
        {inviteSections.tiers.map((tier) => (
          <View key={tier.tierIndex} className='invitations__tier'>
            <View className='invitations__tier-head'>
              <Text className='invitations__tier-title'>{tier.rangeLabel}</Text>
              <Text className='invitations__tier-meta'>
                {tier.validItems.length}/{5} 人
                {tier.isComplete ? ' · 已满档' : ''}
                {tier.rewardGranted ? ' · 已发奖' : ''}
              </Text>
            </View>
            {tier.validItems.length === 0 ? (
              <Text className='invitations__tier-empty'>本档暂无有效邀请</Text>
            ) : (
              tier.validItems.map((item) => (
                <View key={item.id} className='invitations__item invitations__item--nested'>
                  <View className='invitations__item-main'>
                    <Text className='invitations__item-name'>
                      {item.invitee_nickname_masked}
                    </Text>
                    <Text className='invitations__item-date'>
                      {new Date(item.created_at).toLocaleDateString()}
                    </Text>
                  </View>
                  <Text className='invitations__badge invitations__badge--valid'>
                    有效邀请
                  </Text>
                </View>
              ))
            )}
          </View>
        ))}
        {inviteSections.pendingRegistered.length > 0 ? (
          <View className='invitations__tier invitations__tier--pending'>
            <Text className='invitations__tier-title'>待完成首次分析</Text>
            {inviteSections.pendingRegistered.map((item) => (
              <View key={item.id} className='invitations__item invitations__item--nested'>
                <View className='invitations__item-main'>
                  <Text className='invitations__item-name'>
                    {item.invitee_nickname_masked}
                  </Text>
                  <Text className='invitations__item-date'>
                    {new Date(item.created_at).toLocaleDateString()}
                  </Text>
                </View>
                <Text className='invitations__badge invitations__badge--registered'>
                  已注册
                </Text>
              </View>
            ))}
          </View>
        ) : null}
        {list.length === 0 ? (
          <View className='invitations__empty'>
            <Text>还没有邀请记录，试试分享给球友吧</Text>
          </View>
        ) : null}
      </View>
    </View>
  )
}

export default InvitationsPage
