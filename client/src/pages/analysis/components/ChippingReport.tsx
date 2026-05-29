/**
 * 切杆 mode 专属报告区（4 阶段 + 3 维度）
 */

import { FC, useMemo } from 'react'
import { View, Text } from '@tarojs/components'
import type { PhaseScore } from '@/types/analysis'
import RadarChart, { RadarAxis } from '@/components/RadarChart'
import '@/components/RadarChart.scss'
import {
  CHIPPING_FEATURE_LABEL,
  CHIPPING_FEATURE_ORDER,
  CHIPPING_PHASE_LABEL,
  CHIPPING_PHASE_ORDER,
  type ChippingFeatureKey,
  type ChippingPhaseKey,
} from '@/constants/chippingLabels'
import './ChippingReport.scss'

export interface ChippingReportProps {
  phaseScores?: Record<string, PhaseScore> | null
  chippingFeatures?: Record<string, PhaseScore> | null
  onTapPhase?: (phase: ChippingPhaseKey) => void
}

const ChippingReport: FC<ChippingReportProps> = ({
  phaseScores,
  chippingFeatures,
  onTapPhase,
}) => {
  const phaseAxes: RadarAxis[] = useMemo(() => {
    if (!phaseScores) return []
    return CHIPPING_PHASE_ORDER.map((key) => {
      const ps = phaseScores[key]
      return {
        key,
        label: CHIPPING_PHASE_LABEL[key],
        score: ps?.score ?? 0,
        is_weakest: ps?.is_weakest ?? false,
      }
    })
  }, [phaseScores])

  const featureRows = useMemo(() => {
    if (!chippingFeatures) return []
    return CHIPPING_FEATURE_ORDER.map((key) => {
      const ps = chippingFeatures[key as ChippingFeatureKey]
      if (!ps) return null
      return { key, ...ps }
    }).filter(Boolean) as Array<{ key: ChippingFeatureKey; score: number; label: string; is_weakest?: boolean }>
  }, [chippingFeatures])

  return (
    <View className='chipping-report'>
      {phaseAxes.length > 0 && (
        <View className='chipping-report__block'>
          <View className='chipping-report__header'>
            <Text className='chipping-report__title'>切杆四阶段</Text>
            <Text className='chipping-report__hint'>点击顶点查看阶段</Text>
          </View>
          <RadarChart axes={phaseAxes} onTapAxis={(k) => onTapPhase?.(k as ChippingPhaseKey)} />
          <View className='chipping-report__phase-list'>
            {CHIPPING_PHASE_ORDER.map((key) => {
              const ps = phaseScores?.[key]
              if (!ps) return null
              return (
                <View
                  key={key}
                  className={[
                    'chipping-report__phase-item',
                    ps.is_weakest ? 'chipping-report__phase-item--weakest' : '',
                  ]
                    .filter(Boolean)
                    .join(' ')}
                  onClick={() => onTapPhase?.(key)}
                >
                  <Text className='chipping-report__phase-name'>{CHIPPING_PHASE_LABEL[key]}</Text>
                  <Text className='chipping-report__phase-score'>{ps.score}</Text>
                  {ps.is_weakest ? (
                    <Text className='chipping-report__badge'>最需改进</Text>
                  ) : null}
                </View>
              )
            })}
          </View>
        </View>
      )}

      {featureRows.length > 0 && (
        <View className='chipping-report__block'>
          <View className='chipping-report__header'>
            <Text className='chipping-report__title'>切杆三维度</Text>
            <Text className='chipping-report__hint'>幅度 · 杆面 · 触球</Text>
          </View>
          <View className='chipping-report__feature-grid'>
            {featureRows.map((row) => (
              <View
                key={row.key}
                className={[
                  'chipping-report__feature-card',
                  row.is_weakest ? 'chipping-report__feature-card--weakest' : '',
                ]
                  .filter(Boolean)
                  .join(' ')}
              >
                <Text className='chipping-report__feature-label'>
                  {CHIPPING_FEATURE_LABEL[row.key] || row.label}
                </Text>
                <Text className='chipping-report__feature-score'>{row.score}</Text>
                {row.is_weakest ? (
                  <Text className='chipping-report__badge'>最需改进</Text>
                ) : null}
              </View>
            ))}
          </View>
        </View>
      )}
    </View>
  )
}

export default ChippingReport
