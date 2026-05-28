/**
 * 进步曲线 trust tier 图例（P2-W13-A）
 *
 * 跟 ProgressLineChart 圆点配色 1:1 对齐（mint/gold/warning），让用户在曲线
 * 下方看到「mint=AI 高可信 / gold=中等可信 / warning=低可信」三块色块 +
 * 一句话说明。否则单看曲线上点颜色变化，用户不知道含义。
 *
 * 设计要点
 * --------
 * - V1 报告点是默认 accent 色（靛蓝），不显示在图例里（避免让用户
 *   误以为"靛蓝=另一档 trust"）
 * - tier 与 W12-1 / W11 history 卡片完全一致（mint/gold/warning soft 系），
 *   品牌色板已收敛
 * - 仅当传入 ``hasV2Points=true`` 时渲染；调用方对 chartSeries 做
 *   ``.some(p => p.tier)`` 判断
 */

import { FC } from 'react'
import { Text, View } from '@tarojs/components'
import './TrustTierLegend.scss'

export interface TrustTierLegendProps {
  /** 仅当 chart 中存在 V2 报告点时才渲染图例；否则全 V1 报告下展示图例是噪声 */
  hasV2Points: boolean
}

const LEGEND_ITEMS: { key: 'high' | 'medium' | 'low'; label: string; hint: string }[] = [
  { key: 'high', label: '高可信', hint: '画面清晰、机位正、AI 看得清' },
  { key: 'medium', label: '中等可信', hint: '画面够用、可读但有些遮挡或抖动' },
  { key: 'low', label: '低可信', hint: '建议重拍，AI 把握不大' },
]

const TrustTierLegend: FC<TrustTierLegendProps> = ({ hasV2Points }) => {
  if (!hasV2Points) return null
  return (
    <View className='trust-tier-legend'>
      <Text className='trust-tier-legend__title'>曲线点颜色对应 AI 可信度</Text>
      <View className='trust-tier-legend__row'>
        {LEGEND_ITEMS.map((it) => (
          <View key={it.key} className='trust-tier-legend__item'>
            <View className={`trust-tier-legend__dot trust-tier-legend__dot--${it.key}`} />
            <View className='trust-tier-legend__text'>
              <Text className='trust-tier-legend__label'>{it.label}</Text>
              <Text className='trust-tier-legend__hint'>{it.hint}</Text>
            </View>
          </View>
        ))}
      </View>
    </View>
  )
}

export default TrustTierLegend
