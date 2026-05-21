import { FC, useMemo } from 'react'
import { View, Text } from '@tarojs/components'
import Taro from '@tarojs/taro'
import { CLIENT_VERSION } from '@/constants/version'
import './about.scss'

const AboutPage: FC = () => {
  const buildMarker = useMemo(() => {
    return typeof BUILD_MARKER === 'string' ? BUILD_MARKER : 'unknown'
  }, [])

  const goTerms = () => {
    Taro.navigateTo({ url: '/pages/legal/terms' }).catch(() => undefined)
  }
  const goPrivacy = () => {
    Taro.navigateTo({ url: '/pages/legal/privacy' }).catch(() => undefined)
  }
  const goFeedback = () => {
    Taro.navigateTo({ url: '/pages/profile/feedback' }).catch(() => undefined)
  }

  return (
    <View className='about'>
      <View className='about__brand'>
        <Text className='about__title'>领翼golf</Text>
        <Text className='about__subtitle'>AI 高尔夫私教</Text>
      </View>

      <View className='about__meta'>
        <View className='about__row'>
          <Text className='about__label'>版本</Text>
          <Text className='about__value'>v{CLIENT_VERSION}</Text>
        </View>
        <View className='about__row'>
          <Text className='about__label'>构建标识</Text>
          <Text className='about__value about__value--mono'>{buildMarker}</Text>
        </View>
        <View className='about__row'>
          <Text className='about__label'>主体</Text>
          <Text className='about__value'>领翼智能</Text>
        </View>
        <View className='about__row'>
          <Text className='about__label'>ICP 备案</Text>
          <Text className='about__value about__value--muted'>申请中</Text>
        </View>
      </View>

      <View className='about__links'>
        <View className='about__link' onClick={goTerms}>
          <Text className='about__link-label'>用户服务协议</Text>
          <Text className='about__link-arrow'>›</Text>
        </View>
        <View className='about__link' onClick={goPrivacy}>
          <Text className='about__link-label'>隐私政策</Text>
          <Text className='about__link-arrow'>›</Text>
        </View>
        <View className='about__link' onClick={goFeedback}>
          <Text className='about__link-label'>意见反馈</Text>
          <Text className='about__link-arrow'>›</Text>
        </View>
      </View>

      <View className='about__copyright'>
        <Text>© 2026 领翼智能 · 保留所有权利</Text>
      </View>
    </View>
  )
}

export default AboutPage
