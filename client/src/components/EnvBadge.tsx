/**
 * 环境角标（W8-T2）
 *
 * 在 `APP_ENV !== 'production'` 时，于屏幕右上角悬浮显示当前环境
 * （`test` / `local` / 其它）的小标签，防止白名单测试用户把
 * 测试版本误当作正式版反馈。
 *
 * - 仅渲染一个 fixed 小标签，不拦截点击（pointer-events: none）
 * - 生产环境下直接返回 null，零运行时开销
 * - 颜色：深绿主题的反向色（金色），避免与 navigationBar 冲突
 */

import { FC } from 'react'
import { View, Text } from '@tarojs/components'
import './EnvBadge.scss'

const EnvBadge: FC = () => {
  if (APP_ENV === 'production') return null
  const label = APP_ENV || 'local'
  return (
    <View className='env-badge'>
      <Text className='env-badge__text'>{label}</Text>
    </View>
  )
}

export default EnvBadge
