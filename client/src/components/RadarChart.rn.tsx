/**
 * RN 构建：Metro 无法解析微信小程序 Canvas 2d 宿主。
 * 真机绘图需 react-native-svg / Skia 等单独排期；此处保证类型与导出与 weapp 版一致，
 * 报告页可先编过、占位展示轴向分数摘要。
 */

import type { FC } from 'react'
import { View, Text } from '@tarojs/components'

import type { RadarChartProps } from './radar-chart-types'

export type { RadarAxis, RadarChartProps } from './radar-chart-types'

const RadarChart: FC<RadarChartProps> = ({ axes }) => (
  <View className='radar' style={{ minHeight: 200, paddingTop: 16, paddingBottom: 16 }}>
    <Text className='radar__label-name' style={{ textAlign: 'center', marginBottom: 16 }}>
      雷达图 · App 画布适配中（当前为占位）
    </Text>
    {axes.map((ax) => (
      <View key={ax.key} style={{ marginBottom: 8 }}>
        <Text className='radar__label-name'>
          {ax.label}
          {ax.is_weakest ? ' · 重点' : ''}
        </Text>
        <Text className='radar__label-score'>{ax.score}</Text>
      </View>
    ))}
  </View>
)

export default RadarChart
