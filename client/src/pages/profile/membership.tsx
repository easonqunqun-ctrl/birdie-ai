import { FC, useEffect, useMemo, useState } from 'react'
import { View, Text, Button, ScrollView } from '@tarojs/components'
import Taro, { useDidShow } from '@tarojs/taro'
import { paymentService } from '@/services/paymentService'
import { useUserStore } from '@/store/userStore'
import type { Order, PlanOption, PlanType } from '@/types/payment'
import './membership.scss'

const BENEFITS: { label: string; free: string; member: string }[] = [
  { label: '挥杆视频分析', free: '每月 3 次', member: '无限次' },
  { label: 'AI 教练对话', free: '每天 5 轮', member: '无限次' },
  { label: '训练计划', free: '仅查看', member: '完整个性化' },
  { label: '进步曲线', free: '—', member: '✔（W8 开放）' },
  { label: '历史报告对比', free: '—', member: '✔（W8 开放）' }
]

const MembershipPage: FC = () => {
  const { user, fetchMe } = useUserStore()
  const [plans, setPlans] = useState<PlanOption[]>([])
  const [selected, setSelected] = useState<PlanType>('monthly')
  const [orders, setOrders] = useState<Order[]>([])
  const [loading, setLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    load()
  }, [])

  useDidShow(() => {
    fetchMe().catch(() => undefined)
  })

  async function load() {
    setLoading(true)
    try {
      const [planList, orderList] = await Promise.all([
        paymentService.listPlans(),
        paymentService.listMyOrders()
      ])
      setPlans(planList)
      setOrders(orderList)
    } finally {
      setLoading(false)
    }
  }

  async function handleSubscribe() {
    if (submitting) return
    setSubmitting(true)
    try {
      const res = await paymentService.createOrder(selected)
      if (res.mock_mode || PAYMENT_MOCK) {
        const confirmed = await new Promise<boolean>((resolve) => {
          Taro.showModal({
            title: '模拟支付',
            content: `W7 开发模式：点击"模拟支付成功"即刻激活会员。\n金额：${
              plans.find((p) => p.plan_type === selected)?.amount_yuan_display ?? ''
            }`,
            confirmText: '模拟支付',
            cancelText: '取消',
            success: ({ confirm }) => resolve(confirm)
          })
        })
        if (!confirmed) {
          return
        }
        await paymentService.mockConfirm(res.order.id)
      } else {
        // 真实支付（W8 接入）：此处调用 wx.requestPayment(res.prepay_params)
        // 成功后后端通过微信回调将订单置 paid。
        Taro.showToast({ title: '真实支付 W8 接入', icon: 'none' })
        return
      }
      Taro.showToast({ title: '会员已开通', icon: 'success' })
      await fetchMe()
      await load()
    } catch (e) {
      const err = e as Error & { code?: number }
      if (err?.code !== undefined) {
        Taro.showToast({ title: err.message || '支付失败', icon: 'none' })
      }
    } finally {
      setSubmitting(false)
    }
  }

  const headline = useMemo(() => {
    if (!user) return ''
    if (user.is_member) {
      return `${user.membership_type === 'yearly' ? '年度' : '月度'}会员 · 还剩 ${user.membership_days_remaining} 天`
    }
    return '免费用户'
  }, [user])

  const headlineSub = useMemo(() => {
    if (!user) return ''
    if (user.is_member) return '感谢你的支持，继续精进挥杆'
    return '升级会员解锁无限分析与完整训练计划'
  }, [user])

  return (
    <ScrollView className='membership' scrollY>
      <View className={`membership__hero ${user?.is_member ? 'is-member' : ''}`}>
        <Text className='membership__hero-badge'>
          {user?.is_member ? '👑' : '🎯'}
        </Text>
        <Text className='membership__hero-title'>{headline}</Text>
        <Text className='membership__hero-sub'>{headlineSub}</Text>
      </View>

      <View className='membership__plans'>
        {plans.map((p) => {
          const active = p.plan_type === selected
          return (
            <View
              key={p.plan_type}
              className={`membership__plan ${active ? 'is-active' : ''}`}
              onClick={() => setSelected(p.plan_type)}
            >
              <View className='membership__plan-head'>
                <Text className='membership__plan-name'>{p.name}</Text>
                <Text className='membership__plan-price'>{p.amount_yuan_display}</Text>
              </View>
              <Text className='membership__plan-duration'>
                {p.duration_days} 天
              </Text>
              {p.badge && <Text className='membership__plan-badge'>{p.badge}</Text>}
            </View>
          )
        })}
      </View>

      <View className='membership__benefits'>
        <View className='membership__benefits-header'>
          <Text className='membership__benefits-title'>权益对比</Text>
        </View>
        <View className='membership__benefits-row membership__benefits-row--head'>
          <Text className='membership__benefits-col membership__benefits-col--label'>功能</Text>
          <Text className='membership__benefits-col'>免费</Text>
          <Text className='membership__benefits-col'>会员</Text>
        </View>
        {BENEFITS.map((b) => (
          <View key={b.label} className='membership__benefits-row'>
            <Text className='membership__benefits-col membership__benefits-col--label'>{b.label}</Text>
            <Text className='membership__benefits-col'>{b.free}</Text>
            <Text className='membership__benefits-col membership__benefits-col--member'>{b.member}</Text>
          </View>
        ))}
      </View>

      <View className='membership__cta'>
        <Button
          className='membership__btn'
          onClick={handleSubscribe}
          loading={submitting}
          disabled={submitting || loading}
        >
          {user?.is_member ? '续费 / 升级' : '立即开通'}
        </Button>
        <Text className='membership__cta-hint'>
          {PAYMENT_MOCK
            ? 'W7 开发模式：将走模拟支付，无需真实付款'
            : '将通过微信支付完成'}
        </Text>
      </View>

      {orders.length > 0 && (
        <View className='membership__orders'>
          <View className='membership__orders-header'>
            <Text className='membership__orders-title'>订单记录</Text>
          </View>
          {orders.map((o) => (
            <View key={o.id} className='membership__order'>
              <View className='membership__order-main'>
                <Text className='membership__order-name'>
                  {o.plan_type === 'yearly' ? '年度会员' : '月度会员'}
                </Text>
                <Text className={`membership__order-status membership__order-status--${o.status}`}>
                  {o.status === 'paid' ? '已支付' : o.status === 'pending' ? '待支付' : o.status}
                </Text>
              </View>
              <View className='membership__order-meta'>
                <Text className='membership__order-amount'>¥{(o.amount / 100).toFixed(2)}</Text>
                <Text className='membership__order-time'>
                  {o.paid_at ? new Date(o.paid_at).toLocaleString('zh-CN') : new Date(o.created_at).toLocaleString('zh-CN')}
                </Text>
              </View>
            </View>
          ))}
        </View>
      )}
    </ScrollView>
  )
}

export default MembershipPage
