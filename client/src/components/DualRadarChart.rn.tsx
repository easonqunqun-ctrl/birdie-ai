import type { FC } from 'react'
import { View, Text } from '@tarojs/components'

import type { DualRadarChartProps } from './dual-radar-chart-types'

export type { DualRadarChartProps } from './dual-radar-chart-types'

const DualRadarChart: FC<DualRadarChartProps> = ({
  primaryAxes,
  secondaryAxes,
  primaryLabel = '你',
  secondaryLabel = '职业参考',
}) => (
  <View className='dual-radar' style={{ minHeight: 200, padding: 16 }}>
    <Text style={{ textAlign: 'center', marginBottom: 12 }}>
      双雷达 · App 画布适配中
    </Text>
    {primaryAxes.map((ax, i) => {
      const sec = secondaryAxes[i]
      return (
        <View key={ax.key} style={{ marginBottom: 8 }}>
          <Text>
            {ax.label} · {primaryLabel} {ax.score}
            {sec ? ` / ${secondaryLabel} ${sec.score}` : ''}
          </Text>
        </View>
      )
    })}
  </View>
)

export default DualRadarChart
