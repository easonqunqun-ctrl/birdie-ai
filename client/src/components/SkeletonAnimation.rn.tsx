import { FC } from 'react'
import { View, Text } from '@tarojs/components'
import type { SkeletonAnimationProps } from './SkeletonAnimation'

const SkeletonAnimation: FC<SkeletonAnimationProps> = ({ caption }) => (
  <View>
    {caption ? <Text>{caption}</Text> : null}
    <Text>演化示意动画在 RN 端暂未开放，请使用雷达渐变对比。</Text>
  </View>
)

export default SkeletonAnimation
