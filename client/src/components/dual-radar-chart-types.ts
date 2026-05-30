import type { RadarAxis } from './radar-chart-types'

export interface DualRadarChartProps {
  primaryAxes: RadarAxis[]
  secondaryAxes: RadarAxis[]
  /** 同页多实例时须唯一，避免 Canvas id 冲突。 */
  instanceId?: string
  primaryLabel?: string
  secondaryLabel?: string
  /** M12-08：0-1 时在 primary 与 secondary 分数间插值（演化降级）。 */
  morphProgress?: number
}
