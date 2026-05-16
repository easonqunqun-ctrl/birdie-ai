import { FC, useCallback, useEffect, useRef, useState } from 'react'
import { View, Text, Button, Input, Image } from '@tarojs/components'
import Taro, { useDidShow, useRouter } from '@tarojs/taro'
import { useUserStore } from '@/store/userStore'
import { storage } from '@/utils/storage'
import type { User } from '@/types/api'
import { BRAND_LOGO } from '@/constants/brandAssets'
import { describeIntermittentRequestFailure } from '@/services/request'
import './index.scss'

/** 微信要求：带 open-type=agreePrivacyAuthorization 的 button 须设置 id（供隐私回调校验） */
const WX_LOGIN_BUTTON_ID = 'wx-login-btn'

const LoginPage: FC = () => {
  const loginWithWechat = useUserStore((s) => s.loginWithWechat)
  const [agreed, setAgreed] = useState(false)
  const [loading, setLoading] = useState(false)
  /** 防止 agreePrivacy 与 tap 双事件重复提交 */
  const loginLock = useRef(false)
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

  const performLogin = useCallback(async () => {
    if (!agreed) {
      Taro.showToast({ title: '请先勾选协议', icon: 'none' })
      return
    }
    if (loginLock.current) return
    loginLock.current = true
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
      const err = e as Error & { code?: number }
      // request() 已对业务 code≠0 弹过 toast，避免重复打扰
      if (typeof err.code === 'number') {
        loginLock.current = false
        setLoading(false)
        return
      }
      const { toastTitle } = describeIntermittentRequestFailure(e)
      const title =
        toastTitle.length > 48 ? `${toastTitle.slice(0, 47)}…` : toastTitle
      Taro.showToast({ title, icon: 'none', duration: 3200 })
      loginLock.current = false
      setLoading(false)
    }
  }, [agreed, inviteCode, loginWithWechat])

  /** weapp：勿绑 onClick；会与隐私授权竞态，导致 wx.login 在未授权时机调用 */
  const weappLoginButtonProps =
    process.env.TARO_ENV === 'weapp'
      ? ({
          id: WX_LOGIN_BUTTON_ID,
          openType: 'agreePrivacyAuthorization',
          onAgreePrivacyAuthorization: () => {
            void performLogin()
          }
        } as Record<string, unknown>)
      : {}

  return (
    <View className='login'>
      <View className='login__main'>
        <View className='login__brand'>
          <Image
            className='login__logo'
            src={BRAND_LOGO}
            mode='aspectFit'
          />
          <Text className='login__title'>领翼golf</Text>
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
      </View>

      <View className='login__actions'>
        {/*
          协议行在主按钮上方，避免小屏首屏只看到按钮、协议被挤到屏外。
          不用原生 Checkbox：受控 checked + CheckboxGroup 在部分真机/基础库下
          onChange 与 React 状态不同步，界面已勾选但 agreed 仍为 false。
        */}
        <View className='login__agreement'>
          <View
            className={`login__checkbox ${agreed ? 'login__checkbox--checked' : ''}`}
            onClick={() => setAgreed(!agreed)}
          >
            {agreed && <Text className='login__checkbox-mark'>✓</Text>}
          </View>
          <Text
            className='login__agreement-text'
            onClick={() => setAgreed(!agreed)}
          >
            登录即表示同意
          </Text>
          <Text
            className='login__agreement-link'
            onClick={(e) => {
              e.stopPropagation()
              Taro.navigateTo({ url: '/pages/legal/terms' })
            }}
          >
            《用户协议》
          </Text>
          <Text
            className='login__agreement-text'
            onClick={() => setAgreed(!agreed)}
          >
            和
          </Text>
          <Text
            className='login__agreement-link'
            onClick={(e) => {
              e.stopPropagation()
              Taro.navigateTo({ url: '/pages/legal/privacy' })
            }}
          >
            《隐私政策》
          </Text>
        </View>

        <Button
          className='login__btn'
          loading={loading}
          disabled={loading}
          {...(process.env.TARO_ENV === 'weapp'
            ? weappLoginButtonProps
            : { onClick: () => void performLogin() })}
        >
          {loading ? '登录中...' : '微信一键登录'}
        </Button>

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
