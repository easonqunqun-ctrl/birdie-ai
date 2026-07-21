/**
 * 环境角标（W8-T2）
 *
 * 在 `APP_ENV !== 'production'` 时，于屏幕右上角悬浮显示当前环境
 * （`test` / `local` / 其它）的小标签，防止白名单测试用户把
 * 测试版本误当作正式版反馈。
 *
 * - 仅渲染一个 absolute 小标签，不拦截点击
 * - 生产环境下直接返回 null，零运行时开销
 * - RN：top 叠加安全区，避免挡状态栏（小程序 env 由系统处理，inset=0）
 */

import { FC } from 'react'
import { View, Text } from '@tarojs/components'
import { getSafeAreaInsets } from '@/adapters/safeArea'
import './EnvBadge.scss'

declare const BUILD_MARKER: string

/**
 * 从 BUILD_MARKER 取 git short hash。
 * 格式：`{env}@{hash}[+dirty] built {time} UTC`（见 client/config/index.ts）
 */
function shortBuildMarker(): string {
  if (typeof BUILD_MARKER !== 'string' || !BUILD_MARKER) return ''
  const at = BUILD_MARKER.indexOf('@')
  if (at < 0) return ''
  const afterAt = BUILD_MARKER.slice(at + 1)
  const hash = afterAt.split(/[+\s]/)[0]?.trim() || ''
  return hash.slice(0, 12)
}

interface EnvBadgeProps {
  /**
   * app 根统一挂载的全局角标（仅 RN/H5 生效）。
   * RN 上 app.render 会包裹所有页面 → 全局挂一次即可；
   * 各 tabBar 页里的页面级 <EnvBadge/> 在 RN 上跳过，避免重复渲染叠字。
   * 小程序侧 app.render 被忽略，只靠页面级挂载（appRoot 缺省 = false）。
   */
  appRoot?: boolean
}

const EnvBadge: FC<EnvBadgeProps> = ({ appRoot = false }) => {
  if (APP_ENV === 'production') return null
  const isRN = process.env.TARO_ENV === 'rn'
  if (isRN && !appRoot) return null
  if (!isRN && appRoot) return null
  const env = APP_ENV || 'local'
  const marker = shortBuildMarker()
  const label = marker ? `${env}·${marker}` : env
  const inset = getSafeAreaInsets()
  // RN：下移到导航栏（约 44pt）下方，避免压住居中的页面标题；小程序沿用贴顶。
  const top = isRN ? inset.top + 48 : inset.top + 4
  return (
    <View className='env-badge' style={{ top }}>
      <Text className='env-badge__text'>{label}</Text>
    </View>
  )
}

export default EnvBadge
