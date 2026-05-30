/**
 * 六维雷达 DOM 顶点标签的百分比坐标（相对绘图区容器）。
 *
 * r 过大时顶部/底部标签会被父容器裁切或与图例重叠；对正上/正下顶点略向内收。
 */

export interface RadarLabelPosition {
  x: number
  y: number
}

export function computeLabelPositions(axisCount: number): RadarLabelPosition[] {
  if (axisCount <= 0) return []
  const out: RadarLabelPosition[] = []
  const baseR = 46
  for (let i = 0; i < axisCount; i++) {
    const angle = -Math.PI / 2 + (Math.PI * 2 * i) / axisCount
    const cos = Math.cos(angle)
    const sin = Math.sin(angle)
    let r = baseR
    if (sin < -0.75) r -= 6
    else if (sin > 0.75) r -= 10
    else if (Math.abs(cos) > 0.85) r -= 4
    out.push({
      x: 50 + cos * r,
      y: 50 + sin * r,
    })
  }
  return out
}
