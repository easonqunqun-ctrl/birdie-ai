/** 雷达图 props（微信小程序 Canvas 实现与 RN 占位共用类型） */

export interface RadarAxis {
  key: string
  /** 轴标签（显示在顶点外侧） */
  label: string
  /** 分数（0-100） */
  score: number
  /** 是否为弱项（高亮色） */
  is_weakest?: boolean
}

export interface RadarChartProps {
  axes: RadarAxis[]
  /** 点击顶点（或顶点标签）回调 */
  onTapAxis?: (key: string) => void
}
