import { FC, useMemo } from 'react'
import { View, Text, Button } from '@tarojs/components'
import Taro from '@tarojs/taro'
import { useUserStore } from '@/store/userStore'
import { storage } from '@/utils/storage'
import { CLIENT_VERSION } from '@/constants/version'
import './settings.scss'

declare const APP_ENV: string

const SettingsPage: FC = () => {
  const { token, logout } = useUserStore()

  const buildMarker = useMemo(() => {
    return typeof BUILD_MARKER === 'string' ? BUILD_MARKER : 'unknown'
  }, [])
  const showBuildMarker = APP_ENV !== 'production'

  const handleReplayGuide = () => {
    Taro.showModal({
      title: '重新查看拍摄指南',
      content: '下次进入「拍摄分析」时将再次展示拍摄角度、构图与质量说明。是否确认？',
      success: ({ confirm }) => {
        if (!confirm) return
        try {
          storage.clearAnalysisGuideSeen()
          Taro.showToast({ title: '已重置，下次拍摄时展示', icon: 'success' })
        } catch {
          Taro.showToast({ title: '重置失败', icon: 'none' })
        }
      },
    })
  }

  const handleClearCache = () => {
    Taro.showModal({
      title: '清除本地缓存',
      content: '将清空登录状态、协议同意记录与缓存数据，需要重新登录。是否继续？',
      success: ({ confirm }) => {
        if (!confirm) return
        try {
          storage.clearAll()
          logout()
          Taro.showToast({ title: '已清除', icon: 'success' })
          setTimeout(() => {
            Taro.reLaunch({ url: '/pages/login/index' }).catch(() => undefined)
          }, 600)
        } catch {
          Taro.showToast({ title: '清除失败', icon: 'none' })
        }
      },
    })
  }

  const handleLogout = () => {
    Taro.showModal({
      title: '提示',
      content: '确认退出登录？',
      success: ({ confirm }) => {
        if (!confirm) return
        logout()
        Taro.reLaunch({ url: '/pages/login/index' }).catch(() => undefined)
      },
    })
  }

  const goTerms = () => {
    Taro.navigateTo({ url: '/pages/legal/terms' }).catch(() => undefined)
  }

  const goPrivacy = () => {
    Taro.navigateTo({ url: '/pages/legal/privacy' }).catch(() => undefined)
  }

  const goAbout = () => {
    Taro.navigateTo({ url: '/pages/profile/about' }).catch(() => undefined)
  }

  return (
    <View className='settings'>
      <View className='settings__group'>
        <Text className='settings__group-title'>体验</Text>
        <View className='settings__row' onClick={handleReplayGuide}>
          <Text className='settings__row-label'>重新查看拍摄指南</Text>
          <Text className='settings__row-arrow'>›</Text>
        </View>
        <View className='settings__row' onClick={handleClearCache}>
          <Text className='settings__row-label'>清除本地缓存</Text>
          <Text className='settings__row-arrow'>›</Text>
        </View>
      </View>

      <View className='settings__group'>
        <Text className='settings__group-title'>法律与协议</Text>
        <View className='settings__row' onClick={goTerms}>
          <Text className='settings__row-label'>用户服务协议</Text>
          <Text className='settings__row-arrow'>›</Text>
        </View>
        <View className='settings__row' onClick={goPrivacy}>
          <Text className='settings__row-label'>隐私政策</Text>
          <Text className='settings__row-arrow'>›</Text>
        </View>
        <View className='settings__row' onClick={goAbout}>
          <Text className='settings__row-label'>关于领翼golf</Text>
          <Text className='settings__row-value'>v{CLIENT_VERSION}</Text>
          <Text className='settings__row-arrow'>›</Text>
        </View>
      </View>

      {showBuildMarker && (
        <View className='settings__group'>
          <Text className='settings__group-title'>构建</Text>
          <View className='settings__row settings__row--static'>
            <Text className='settings__row-label'>构建标识</Text>
            <Text className='settings__row-value settings__row-value--mono'>
              {buildMarker}
            </Text>
          </View>
        </View>
      )}

      {token ? (
        <View className='settings__actions'>
          <Button
            className='settings__btn settings__btn--ghost'
            onClick={handleLogout}
          >
            退出登录
          </Button>
        </View>
      ) : null}
    </View>
  )
}

export default SettingsPage
