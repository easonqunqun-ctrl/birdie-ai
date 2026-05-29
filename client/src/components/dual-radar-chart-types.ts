import type { RadarAxis } from './radar-chart-types'

export interface DualRadarChartProps {
  primaryAxes: RadarAxis[]
  secondaryAxes: RadarAxis[]
  primaryLabel?: string
  secondaryLabel?: string
  /** M12-08：0-1 时在 primary 与 secondary 分数间插值（演化降级）。 */
  morphProgress?: number
}
