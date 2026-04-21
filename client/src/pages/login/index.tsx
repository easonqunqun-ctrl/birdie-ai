import { FC, useEffect, useState } from 'react'
import { View, Text, Button, Input } from '@tarojs/components'
import Taro, { useDidShow, useRouter } from '@tarojs/taro'
import { useUserStore } from '@/store/userStore'
import { storage } from '@/utils/storage'
import type { User } from '@/types/api'
import './index.scss'

const LoginPage: FC = () => {
  const loginWithWechat = useUserStore((s) => s.loginWithWechat)
  const [agreed, setAgreed] = useState(false)
  const [loading, setLoading] = useState(false)
  // W7-T4：邀请码可选，折叠输入；绑定后 inviter/invitee 各 +1 次分析
  const [showInvite, setShowInvite] = useState(false)
  const [inviteCode, setInviteCode] = useState('')
  // 小程序从分享链接唤起时带 invite_code=XXX，自动展开并预填
  const router = useRouter()
  useEffect(() => {
    const codeFromShare = router.params?.invite_code
    if (codeFromShare) {
      setInviteCode(codeFromShare.toUpperCase())
      setShowInvite(true)
    }
  }, [router.params?.invite_code])

  /**
   * 进入守卫：若本地已有 Token 且用户已完成引导，直接跳首页。
   * 处理"401 清 Token 后 reLaunch 到 login → 又被外部路径唤起"的边界，
   * 以及开发时手动从其他 tab 切回 login 的情况。
   */
  useDidShow(() => {
    const token = storage.getToken()
    if (!token) return
    const cached = storage.getUser<User>()
    if (cached?.onboarding_completed) {
      Taro.reLaunch({ url: '/pages/index/index' })
    } else if (cached) {
      Taro.reLaunch({ url: '/pages/onboarding/index' })
    }
  })

  const handleLogin = async () => {
    if (!agreed) {
      Taro.showToast({ title: '请先勾选协议', icon: 'none' })
      return
    }
    setLoading(true)
    try {
      const trimmed = inviteCode.trim().toUpperCase()
      const { isNewUser, user } = await loginWithWechat(
        trimmed ? trimmed : undefined
      )
      // 路由分流：新用户 或 老用户未完成引导 → onboarding；否则 → 首页。
      // 合并判断避免先跳 index 再跳 onboarding 的双次 reLaunch 闪屏。
      const needsOnboarding = isNewUser || !user.onboarding_completed
      Taro.reLaunch({
        url: needsOnboarding ? '/pages/onboarding/index' : '/pages/index/index'
      })
      // 不在 finally 里复位 loading：reLaunch 后组件即将卸载，
      // 复位会触发 React 对已卸载组件 setState 的 warning。
    } catch (e) {
      console.warn('login failed', e)
      setLoading(false)
    }
  }

  return (
    <View className='login'>
      <View className='login__brand'>
        <Text className='login__logo'>🐦</Text>
        <Text className='login__title'>小鸟 AI</Text>
        <Text className='login__slogan'>你的随身高尔夫智能教练</Text>
      </View>

      <View className='login__features'>
        <View className='login__feature'>
          <Text className='login__feature-icon'>📹</Text>
          <Text className='login__feature-text'>AI 挥杆分析，30 秒出报告</Text>
        </View>
        <View className='login__feature'>
          <Text className='login__feature-icon'>💬</Text>
          <Text className='login__feature-text'>24 小时 AI 教练在线问答</Text>
        </View>
        <View className='login__feature'>
          <Text className='login__feature-icon'>📈</Text>
          <Text className='login__feature-text'>个性化训练方案</Text>
        </View>
      </View>

      <View className='login__actions'>
        <Button
          className='login__btn'
          loading={loading}
          disabled={loading}
          onClick={handleLogin}
        >
          {loading ? '登录中...' : '微信一键登录'}
        </Button>

        <View className='login__agreement' onClick={() => setAgreed(!agreed)}>
          <View className={`login__checkbox ${agreed ? 'login__checkbox--checked' : ''}`}>
            {agreed && <Text>✓</Text>}
          </View>
          <Text className='login__agreement-text'>
            登录即表示同意《用户协议》和《隐私政策》
          </Text>
        </View>

        <View className='login__invite'>
          {!showInvite ? (
            <Text
              className='login__invite-toggle'
              onClick={() => setShowInvite(true)}
            >
              有邀请码？点击填写（可选）
            </Text>
          ) : (
            <View className='login__invite-form'>
              <Input
                className='login__invite-input'
                value={inviteCode}
                onInput={(e) => setInviteCode(e.detail.value.toUpperCase())}
                placeholder='请输入 8 位邀请码'
                maxlength={8}
                disabled={loading}
              />
              <Text className='login__invite-tip'>
                使用邀请码：你与邀请人本月各 +1 次分析
              </Text>
            </View>
          )}
        </View>
      </View>
    </View>
  )
}

export default LoginPage
