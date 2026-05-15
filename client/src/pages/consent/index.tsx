/**
 * 首启合规拦截页（W8-T1）
 *
 * 展示时机：
 *   `App.onLaunch` 检测本地 `agreed_terms` 与 `CURRENT_TERMS_VERSION` 不一致时
 *   reLaunch 到本页。同意即写入本地存储并 **`reLaunch` 首页（访客可先浏览）**；拒绝则留在本页。
 *
 * 注意：
 *   - 本页本身不请求任何隐私 API，因此**不触发**微信隐私运行时授权；
 *     `wx.login` 在登录页由带 `open-type=agreePrivacyAuthorization` 的按钮触发；
 *     `chooseMedia` 在拍摄页等调用前由 `utils/privacy.ts::ensurePrivacyAuthorized` 守卫。
 *   - 协议正文跳转到 `pages/legal/terms`、`pages/legal/privacy` 两个独立页，
 *     便于"我的 → 关于"入口复用。
 */

import { FC, useState } from 'react'
import { View, Text, Button, Image } from '@tarojs/components'
import Taro from '@tarojs/taro'
import { storage, CURRENT_TERMS_VERSION } from '@/utils/storage'
import { BRAND_LOGO } from '@/constants/brandAssets'
import './index.scss'

const ConsentPage: FC = () => {
  const [rejected, setRejected] = useState(false)

  const openTerms = () => {
    Taro.navigateTo({ url: '/pages/legal/terms' })
  }
  const openPrivacy = () => {
    Taro.navigateTo({ url: '/pages/legal/privacy' })
  }

  const handleAgree = () => {
    storage.setAgreedTerms(CURRENT_TERMS_VERSION)
    // 微信审核：须先让用户浏览产品与协议入口，不得在同意隐私后立刻挡在登录授权页。
    Taro.reLaunch({ url: '/pages/index/index' })
  }

  const handleReject = () => {
    setRejected(true)
    Taro.showToast({
      title: '不同意将无法使用本产品',
      icon: 'none',
      duration: 2000
    })
  }

  return (
    <View className='consent'>
      <View className='consent__main'>
        <View className='consent__brand'>
          <Image
            className='consent__logo'
            src={BRAND_LOGO}
            mode='aspectFit'
          />
          <Text className='consent__title'>欢迎使用领翼golf</Text>
          <Text className='consent__slogan'>你的随身高尔夫智能教练</Text>
        </View>

        <View className='consent__card'>
          <Text className='consent__card-title'>在开始之前</Text>
        <Text className='consent__card-text'>
          我们非常重视你的个人信息保护。使用本产品，我们需要收集：
        </Text>
        <View className='consent__list'>
          <Text className='consent__item'>
            <Text className='consent__highlight'>微信 OpenID</Text>
            ：用于账号登录与标识（由微信授权获取，我们无法单独获取到你的微信号）。
          </Text>
          <Text className='consent__item'>
            <Text className='consent__highlight'>挥杆视频</Text>
            ：仅在你主动拍摄/选择后上传，用于 AI 分析并生成报告。
          </Text>
          <Text className='consent__item'>
            <Text className='consent__highlight'>对话内容</Text>
            ：用于 AI 教练问答；会通过国内合规 LLM 通道生成回复。
          </Text>
        </View>
        <Text className='consent__card-text'>
          {`所有数据均存储在中国境内服务器，采用加密传输与存储。你可在"我的"页面随时查看、删除或注销账号。`}
        </Text>
      </View>

      <View className='consent__links'>
        请阅读并同意
        <Text className='consent__link' onClick={openTerms}>
          《用户服务协议》
        </Text>
        与
        <Text className='consent__link' onClick={openPrivacy}>
          《隐私政策》
        </Text>
      </View>
      </View>

      <View className='consent__bottom'>
        <View className='consent__actions'>
          <Button className='consent__btn-primary' onClick={handleAgree}>
            同意并继续
          </Button>
          <Button className='consent__btn-secondary' onClick={handleReject}>
            暂不同意
          </Button>
        </View>

        {rejected && (
          <Text className='consent__reject-hint'>
            若暂不同意，请退出小程序。你可以随时重新进入并选择同意。
          </Text>
        )}
      </View>
    </View>
  )
}

export default ConsentPage
