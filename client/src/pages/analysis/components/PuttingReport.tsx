/**
 * 推杆 mode 专属报告区（4 阶段 + 4 维度）
 */

import { FC, useMemo } from 'react'
import { View, Text } from '@tarojs/components'
import type { PhaseScore } from '@/types/analysis'
import RadarChart, { RadarAxis } from '@/components/RadarChart'
import '@/components/RadarChart.scss'
import {
  PUTTING_FEATURE_LABEL,
  PUTTING_FEATURE_ORDER,
  PUTTING_PHASE_LABEL,
  PUTTING_PHASE_ORDER,
  type PuttingFeatureKey,
  type PuttingPhaseKey,
} from '@/constants/puttingLabels'
import './PuttingReport.scss'

export interface PuttingReportProps {
  phaseScores?: Record<string, PhaseScore> | null
  puttingFeatures?: Record<string, PhaseScore> | null
  onTapPhase?: (phase: PuttingPhaseKey) => void
}

const PuttingReport: FC<PuttingReportProps> = ({
  phaseScores,
  puttingFeatures,
  onTapPhase,
}) => {
  const phaseAxes: RadarAxis[] = useMemo(() => {
    if (!phaseScores) return []
    return PUTTING_PHASE_ORDER.map((key) => {
      const ps = phaseScores[key]
      return {
        key,
        label: PUTTING_PHASE_LABEL[key],
        score: ps?.score ?? 0,
        is_weakest: ps?.is_weakest ?? false,
      }
    })
  }, [phaseScores])

  const featureRows = useMemo(() => {
    if (!puttingFeatures) return []
    return PUTTING_FEATURE_ORDER.map((key) => {
      const ps = puttingFeatures[key as PuttingFeatureKey]
      if (!ps) return null
      return { key, ...ps }
    }).filter(Boolean) as Array<{ key: PuttingFeatureKey; score: number; label: string; is_weakest?: boolean }>
  }, [puttingFeatures])

  return (
    <View className='putting-report'>
      {phaseAxes.length > 0 && (
        <View className='putting-report__block'>
          <View className='putting-report__header'>
            <Text className='putting-report__title'>推杆四阶段</Text>
            <Text className='putting-report__hint'>点击顶点查看阶段</Text>
          </View>
          <RadarChart axes={phaseAxes} onTapAxis={(k) => onTapPhase?.(k as PuttingPhaseKey)} />
          <View className='putting-report__phase-list'>
            {PUTTING_PHASE_ORDER.map((key) => {
              const ps = phaseScores?.[key]
              if (!ps) return null
              return (
                <View
                  key={key}
                  className={[
                    'putting-report__phase-item',
                    ps.is_weakest ? 'putting-report__phase-item--weakest' : '',
                  ]
                    .filter(Boolean)
                    .join(' ')}
                  onClick={() => onTapPhase?.(key)}
                >
                  <Text className='putting-report__phase-name'>{PUTTING_PHASE_LABEL[key]}</Text>
                  <Text className='putting-report__phase-score'>{ps.score}</Text>
                  {ps.is_weakest ? (
                    <Text className='putting-report__badge'>最需改进</Text>
                  ) : null}
                </View>
              )
            })}
          </View>
        </View>
      )}

      {featureRows.length > 0 && (
        <View className='putting-report__block'>
          <View className='putting-report__header'>
            <Text className='putting-report__title'>推杆四维度</Text>
            <Text className='putting-report__hint'>钟摆 · 头部 · 杆面 · 节奏</Text>
          </View>
          <View className='putting-report__feature-grid'>
            {featureRows.map((row) => (
              <View
                key={row.key}
                className={[
                  'putting-report__feature-card',
                  row.is_weakest ? 'putting-report__feature-card--weakest' : '',
                ]
                  .filter(Boolean)
                  .join(' ')}
              >
                <Text className='putting-report__feature-label'>
                  {PUTTING_FEATURE_LABEL[row.key] || row.label}
                </Text>
                <Text className='putting-report__feature-score'>{row.score}</Text>
                {row.is_weakest ? (
                  <Text className='putting-report__badge'>最需改进</Text>
                ) : null}
              </View>
            ))}
          </View>
        </View>
      )}
    </View>
  )
}

export default PuttingReport
