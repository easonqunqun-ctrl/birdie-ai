import type { RadarAxis } from './radar-chart-types'

export interface DualRadarChartProps {
  primaryAxes: RadarAxis[]
  secondaryAxes: RadarAxis[]
  primaryLabel?: string
  secondaryLabel?: string
}
