import { FC, useEffect, useMemo, useState } from 'react'
import { View, Text, Button, ScrollView, Switch } from '@tarojs/components'
import Taro, { useDidShow } from '@tarojs/taro'
import { paymentService } from '@/services/paymentService'
import { requestWechatPayment } from '@/adapters/payment'
import { describeIntermittentRequestFailure, describePageLoadFailure, isRequestError } from '@/services/request'
import { useUserStore } from '@/store/userStore'
import { PAYMENT_ENABLED_FLAG, PAYMENT_MOCK_FLAG } from '@/constants/flags'
import { SUBSCRIBE_TPL_MEMBERSHIP_EXPIRE, SUBSCRIBE_TPL_MEMBERSHIP_PRE_EXPIRE } from '@/constants/subscribeTemplates'
import { useMembershipExpiringSoonModal } from '@/hooks/useMembershipExpiringSoonModal'
import type { MembershipInfo } from '@/types/payment'
import { track } from '@/utils/track'
import type { Order, PlanOption, PlanType } from '@/types/payment'
import './membership.scss'

const BENEFITS: { label: string; free: string; member: string }[] = [
  { label: '挥杆视频分析', free: '每月 3 次', member: '无限次' },
  { label: 'AI 教练对话', free: '每天 5 轮', member: '无限次' },
  { label: '训练计划', free: '仅查看', member: '完整个性化' },
  { label: '进步曲线', free: '—', member: '✔（正式版开放）' },
  { label: '历史报告对比', free: '—', member: '✔（正式版开放）' }
]

const MembershipPage: FC = () => {
  const { user, fetchMe } = useUserStore()
  const [plans, setPlans] = useState<PlanOption[]>([])
  const [selected, setSelected] = useState<PlanType>('monthly')
  const [orders, setOrders] = useState<Order[]>([])
  const [loading, setLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [memInfo, setMemInfo] = useState<MembershipInfo | null>(null)
  const [memBusy, setMemBusy] = useState(false)

  async function refreshMembershipInfo() {
    try {
      const m = await paymentService.getMembership()
      setMemInfo(m)
    } catch {
      /* 非致命：页面其它区块仍可展示 */
    }
  }

  useEffect(() => {
    load()
    void refreshMembershipInfo()
  }, [])

  useDidShow(() => {
    fetchMe().catch(() => undefined)
    void refreshMembershipInfo()
  })

  // 站内弹窗：剩余 [1, 7] 天且当日未弹过时引导续费（不依赖订阅消息授权，docs/02 §1.4.3 配套）
  useMembershipExpiringSoonModal(memInfo)

  async function load() {
    setLoading(true)
    try {
      const [planList, orderList] = await Promise.all([
        paymentService.listPlans(),
        paymentService.listMyOrders()
      ])
      setPlans(planList)
      setOrders(orderList)
    } catch (e: unknown) {
      const raw = describePageLoadFailure(e)
      const title = raw.length > 220 ? `${raw.slice(0, 217)}…` : raw
      Taro.showToast({
        title,
        icon: 'none',
      })
    } finally {
      setLoading(false)
    }
  }

  /** 须用户点击触发（微信平台要求）；未配置 `TARO_APP_SUBSCRIBE_TMPL_IDS` 第 2 项则无操作 */
  function handleSubscribeMembershipExpireNotify() {
    if (TARO_BUILD_TARGET !== 'weapp') return
    const tid = SUBSCRIBE_TPL_MEMBERSHIP_EXPIRE
    if (!tid) {
      Taro.showToast({ title: '暂未配置到期提醒模板', icon: 'none' })
      return
    }
    void Taro.requestSubscribeMessage({ tmplIds: [tid], entityIds: [] }).catch(
      () => {}
    )
  }

  /** 须用户点击触发（微信平台要求）；未配置 `TARO_APP_SUBSCRIBE_TMPL_IDS` 第 3 项则无操作 */
  function handleSubscribePreExpireNotify() {
    if (TARO_BUILD_TARGET !== 'weapp') return
    const tid = SUBSCRIBE_TPL_MEMBERSHIP_PRE_EXPIRE
    if (!tid) {
      Taro.showToast({ title: '暂未配置即将到期模板', icon: 'none' })
      return
    }
    void Taro.requestSubscribeMessage({ tmplIds: [tid], entityIds: [] }).catch(() => {})
  }

  async function handleAutoRenewChange(next: boolean) {
    if (memBusy) return
    // 关闭路径：二次确认 + 调独立端点 `POST /v1/payments/membership/cancel-auto-renew`
    // （docs/02 §6.5）。响应携带 expires_at，UI 可直接展示"会员有效期至 YYYY-MM-DD"。
    if (!next && memInfo?.auto_renew) {
      const confirmed = await new Promise<boolean>((resolve) => {
        Taro.showModal({
          title: '关闭自动续费？',
          content:
            '关闭后到期前不会再自动扣款。当前会员权益在有效期内继续可用，到期后回到免费版。',
          confirmText: '关闭',
          cancelText: '不关',
          success: ({ confirm }) => resolve(confirm),
        })
      })
      if (!confirmed) return
      setMemBusy(true)
      try {
        const res = await paymentService.postCancelAutoRenew()
        const expiry = res.expires_at
          ? new Date(res.expires_at).toLocaleDateString('zh-CN')
          : ''
        Taro.showToast({
          title: expiry ? `已关闭，会员至 ${expiry}` : '已关闭自动续费',
          icon: 'success',
        })
        await refreshMembershipInfo()
        await fetchMe()
      } catch (e: unknown) {
        if (isRequestError(e)) {
          Taro.showToast({
            title: (e.message || '关闭失败').slice(0, 220),
            icon: 'none',
          })
        } else {
          Taro.showToast({
            title: describeIntermittentRequestFailure(e).toastTitle,
            icon: 'none',
          })
        }
      } finally {
        setMemBusy(false)
      }
      return
    }
    // 开启路径 / 其他：沿用通用 toggle 接口（mock 模式直接落库；真实模式返回 papay 跳转参数）
    setMemBusy(true)
    try {
      const res = await paymentService.postAutoRenew(next)
      if (res.papay_sign && TARO_BUILD_TARGET === 'weapp' && next) {
        const { pre_entrustweb_id, redirect_appid, redirect_path } = res.papay_sign
        const sep = redirect_path.includes('?') ? '&' : '?'
        const path = `${redirect_path}${sep}pre_entrustweb_id=${encodeURIComponent(pre_entrustweb_id)}`
        await Taro.navigateToMiniProgram({
          appId: redirect_appid,
          path,
        })
      }
      await refreshMembershipInfo()
      await fetchMe()
    } catch (e: unknown) {
      if (isRequestError(e)) {
        Taro.showToast({
          title: (e.message || '操作失败').slice(0, 220),
          icon: 'none',
        })
      } else {
        Taro.showToast({
          title: describeIntermittentRequestFailure(e).toastTitle,
          icon: 'none',
        })
      }
    } finally {
      setMemBusy(false)
    }
  }

  async function handleSubscribe() {
    if (submitting) return
    setSubmitting(true)
    try {
      let wxLoginCode: string | undefined
      if (TARO_BUILD_TARGET === 'weapp' && !PAYMENT_MOCK_FLAG) {
        const lr = await Taro.login()
        if (!lr.code) {
          Taro.showToast({ title: '微信登录失败，请重试', icon: 'none' })
          return
        }
        wxLoginCode = lr.code
      }
      const res = await paymentService.createOrder(selected, wxLoginCode)
      // 必须与后端 `CreateOrderResponse.mock_mode` 一致：编译期 PAYMENT_MOCK 默认 true，
      // 若此处再用 PAYMENT_MOCK_FLAG「或」进来，会在服务端已关闭模拟支付时仍走 mockConfirm → 40013。
      if (res.mock_mode) {
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
        const pp = res.prepay_params
        try {
          await requestWechatPayment({
            ...pp,
            payment_method: pp.payment_method || (res.virtual_pay_enabled ? 'virtual' : 'jsapi'),
          })
        } catch (payErr: unknown) {
          const m = (payErr as { errMsg?: string })?.errMsg || ''
          if (/cancel/i.test(m) || m.includes('cancel')) {
            Taro.showToast({ title: '已取消', icon: 'none' })
          } else {
            const fromWx =
              m.replace(/^request(Virtual)?Payment:fail\s*/i, '').trim() || ''
            let title =
              fromWx.length > 0 && fromWx.length <= 220
                ? fromWx
                : describeIntermittentRequestFailure(payErr).toastTitle
            if (/iOS支付|尚未开启iOS/i.test(fromWx)) {
              title =
                'iOS 支付需在 mp 后台「虚拟支付 → iOS资金概况」完成签约；签约后使用现网 env=0 重试'
            }
            Taro.showToast({ title, icon: 'none', duration: 3200 })
          }
          return
        }
        Taro.showLoading({ title: '确认中...', mask: true })
        try {
          try {
            await paymentService.syncFromWechat(res.order.id)
          } catch {
            /* 网络或短暂错误：仍靠下方轮询 /users/me */
          }
          for (let i = 0; i < 10; i++) {
            await fetchMe()
            const m = useUserStore.getState().user?.is_member
            if (m) break
            await new Promise<void>((r) => setTimeout(r, 800))
          }
        } finally {
          Taro.hideLoading()
        }
      }
      await fetchMe()
      const becameMember = !!useUserStore.getState().user?.is_member
      const mode: 'mock' | 'real' | 'real_pending' = res.mock_mode
        ? 'mock'
        : becameMember
          ? 'real'
          : 'real_pending'
      track('pay_success', {
        order_id: res.order.id,
        plan_type: selected,
        amount: plans.find((p) => p.plan_type === selected)?.amount_yuan_display ?? '',
        mode
      })
      Taro.showToast({
        title: becameMember
          ? '会员已开通'
          : '支付已提交，请稍后在「我的」下拉刷新',
        icon: becameMember ? 'success' : 'none',
      })
      await load()
    } catch (e) {
      if (isRequestError(e)) {
        if (e.kind === 'network') {
          Taro.showToast({
            title: describeIntermittentRequestFailure(e).toastTitle,
            icon: 'none',
          })
        } else if (e.kind === 'business' || e.kind === 'http_server_error') {
          const lines = [e.message || '请求失败']
          if (e.detail) lines.push(e.detail)
          const content = lines.filter(Boolean).join('\n\n').slice(0, 3500)
          Taro.showModal({
            title: '开通失败',
            content,
            showCancel: false,
          })
        } else {
          Taro.showToast({
            title: describeIntermittentRequestFailure(e).toastTitle,
            icon: 'none',
          })
        }
        return
      }
      Taro.showToast({
        title: describeIntermittentRequestFailure(e).toastTitle,
        icon: 'none',
      })
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
      <View className='membership__inner'>
      {/*
        W8-T3：PAYMENT_ENABLED=false 时本页是"管理员/QA 入口"，
          普通内测用户不应该出现在这里（profile 页的入口已经隐藏）。
          顶部 banner 明示当前是内测阶段、付费功能未开放，避免会员状态/订单
          数据被误读。
        W9 上线（PAYMENT_ENABLED=true）后该 banner 自动消失。
      */}
      {!PAYMENT_ENABLED_FLAG && (
        <View className='membership__notice'>
          <Text className='membership__notice-text'>
            内测阶段·付费功能未开放，所有用户均按「无限」配额体验
          </Text>
        </View>
      )}
      <View className={`membership__hero ${user?.is_member ? 'is-member' : ''}`}>
        <Text className='membership__hero-badge'>
          {user?.is_member ? '👑' : '🎯'}
        </Text>
        <Text className='membership__hero-title'>{headline}</Text>
        <Text className='membership__hero-sub'>{headlineSub}</Text>
      </View>

      {user?.is_member && PAYMENT_ENABLED_FLAG && !memInfo?.virtual_pay_enabled && (
        <View className='membership__renew-card'>
          <View className='membership__renew-row'>
            <View className='membership__renew-texts'>
              <Text className='membership__renew-title'>自动续费</Text>
              <Text className='membership__renew-desc'>
                {PAYMENT_MOCK_FLAG
                  ? '联调模式：开关将直接保存意向。'
                  : memInfo?.papay_contract_id
                    ? '已签约微信委托代扣，到期前将按规则发起续费（以微信支付结果为准）。'
                    : '开启后将跳转微信支付小程序完成委托代扣签约。'}
              </Text>
            </View>
            <Switch
              color='#1a237e'
              checked={!!memInfo?.auto_renew}
              disabled={memBusy}
              onChange={(e) => void handleAutoRenewChange(e.detail.value)}
            />
          </View>
        </View>
      )}

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
        {TARO_BUILD_TARGET === 'weapp' &&
          user?.is_member &&
          SUBSCRIBE_TPL_MEMBERSHIP_EXPIRE && (
            <Button
              className='membership__btn membership__btn--subscribe-notify'
              onClick={handleSubscribeMembershipExpireNotify}
            >
              接收会员到期提醒（微信通知，需点此授权）
            </Button>
          )}
        {TARO_BUILD_TARGET === 'weapp' &&
          user?.is_member &&
          SUBSCRIBE_TPL_MEMBERSHIP_PRE_EXPIRE && (
            <Button
              className='membership__btn membership__btn--subscribe-notify'
              onClick={handleSubscribePreExpireNotify}
            >
              接收「即将到期」提醒（第三模板，需点此授权）
            </Button>
          )}
        <Text className='membership__cta-hint'>
          {PAYMENT_MOCK_FLAG
            ? '联调构建默认开启模拟开关：真实下单仍以服务端为准（关闭后端模拟时将拉起微信支付）'
            : memInfo?.virtual_pay_enabled
              ? '将通过小程序虚拟支付完成（iOS 合规）'
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
      </View>
    </ScrollView>
  )
}

export default MembershipPage
