/**
 * 综合分与维度分说明（对齐 docs/20 §4.2～§4.3，用户可见帮助）
 */

import { FC } from 'react'
import { View, Text, ScrollView } from '@tarojs/components'
import './score-guide.scss'

const ScoreGuidePage: FC = () => {
  return (
    <ScrollView scrollY className='legal legal--terms'>
      <View className='legal__inner'>
        <View className='legal__header'>
          <Text className='legal__title'>分数说明</Text>
          <Text className='legal__meta'>帮助您理解报告上的得分</Text>
        </View>

        <View className='legal__section'>
          <Text className='legal__section-title'>分数表示什么</Text>
          <Text className='legal__paragraph'>
            在当期算法版本中，综合分与各维度分表示： 在当前视频里
            <Text className='legal__item-title'>软件能够看清</Text>
            的前提下，您的挥杆动作与领翼golf 采用的「结构化理想挥杆模型」之间的
            <Text className='legal__item-title'>贴合程度</Text>
            ，并综合若干可计算的几何与节奏特征。
          </Text>
          <Text className='legal__paragraph'>
            <Text className='legal__item-title'>分数越高</Text>
            ，表示与当前模型的一致性越好。更适合用于
            <Text className='legal__item-title'>同一人在相近条件下多次拍摄</Text>
            的纵向对比，以及找出相对薄弱的维度；不必过度纠结单次绝对值。
          </Text>
        </View>

        <View className='legal__section'>
          <Text className='legal__section-title'>分数不表示什么</Text>
          <View className='legal__list'>
            <Text className='legal__item'>
              不是世界排名，也不是对名人或选手的「强弱评判」。
            </Text>
            <Text className='legal__item'>
              不能替代球场杆数、比赛成绩或教练的现场综合判断。
            </Text>
            <Text className='legal__item'>
              在机位不佳、身体未完整入镜、光线过暗或挥杆被遮挡时，分数可能不稳定；
              建议按拍摄引导重新录制后再看报告。
            </Text>
          </View>
        </View>

        <View className='legal__section'>
          <Text className='legal__section-title'>如何更好地使用分数</Text>
          <Text className='legal__paragraph'>
            建议您在
            <Text className='legal__item-title'>相近日期、相似拍摄条件</Text>
            下多拍几次，观察分数与诊断的
            <Text className='legal__item-title'>变化趋势</Text>
            ，往往比盯着单次分数更有参考价值。
          </Text>
        </View>

        <View className='legal__section'>
          <Text className='legal__section-title'>其他常见问题</Text>
          <Text className='legal__paragraph legal__item-title'>顶尖选手的视频分数看起来不高？</Text>
          <Text className='legal__paragraph'>
            许多职业球员有强烈的个人技术特点，在「标准模型」下可能出现看似偏低的分数，
            但这不代表其竞技水平弱于模型。我们会持续通过样本校准缩小观感与分数的割裂。
          </Text>
          <Text className='legal__paragraph legal__item-title'>和线下教练结论不一致？</Text>
          <Text className='legal__paragraph'>
            AI 主要从可见的几何与节奏信息给出参考；教练可能还会结合球路、策略与现场观察。
            若结论冲突，请以线下教练为准；您也可以拿着报告里的维度与教练一起讨论。
          </Text>
        </View>

        <Text className='legal__footer'>
          如需更多帮助，可通过「我的」中的意见反馈联系我们。
        </Text>
      </View>
    </ScrollView>
  )
}

export default ScoreGuidePage
