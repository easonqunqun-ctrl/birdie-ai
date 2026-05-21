import { FC, useMemo } from 'react'
import { View, Text } from '@tarojs/components'
import Taro from '@tarojs/taro'
import { CLIENT_VERSION } from '@/constants/version'
import './about.scss'

declare const APP_ENV: string

const ICP_FILING = '京ICP备2026023735号'

const AboutPage: FC = () => {
  const buildMarker = useMemo(() => {
    return typeof BUILD_MARKER === 'string' ? BUILD_MARKER : 'unknown'
  }, [])
  const showBuildMarker = APP_ENV !== 'production'

  const goTerms = () => {
    Taro.navigateTo({ url: '/pages/legal/terms' }).catch(() => undefined)
  }
  const goPrivacy = () => {
    Taro.navigateTo({ url: '/pages/legal/privacy' }).catch(() => undefined)
  }
  const goFeedback = () => {
    Taro.navigateTo({ url: '/pages/profile/feedback' }).catch(() => undefined)
  }

  // 给最终用户隐藏构建水印，但保留长按版本号显示一次（debug 友好）
  const onVersionLongPress = () => {
    Taro.showModal({
      title: '构建信息',
      content: buildMarker,
      showCancel: false,
      confirmText: '我知道了',
    }).catch(() => undefined)
  }

  return (
    <View className='about'>
      <View className='about__brand'>
        <Text className='about__title'>领翼golf</Text>
        <Text className='about__subtitle'>AI 高尔夫私教</Text>
      </View>

      <View className='about__meta'>
        <View className='about__row' onLongPress={onVersionLongPress}>
          <Text className='about__label'>版本</Text>
          <Text className='about__value'>v{CLIENT_VERSION}</Text>
        </View>
        {showBuildMarker && (
          <View className='about__row'>
            <Text className='about__label'>构建标识</Text>
            <Text className='about__value about__value--mono'>{buildMarker}</Text>
          </View>
        )}
        <View className='about__row'>
          <Text className='about__label'>主体</Text>
          <Text className='about__value'>领翼智能</Text>
        </View>
        <View className='about__row'>
          <Text className='about__label'>ICP 备案</Text>
          <Text className='about__value'>{ICP_FILING}</Text>
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
