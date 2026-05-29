/**
 * P2-M12-08 · 2D 骨骼关键点线性插值（best-effort 演化动画）。
 */

export interface Pose2D {
  x: number
  y: number
}

export type PoseKeypoints = Pose2D[]

/** 简化 9 点 stick figure 连线（head→neck→肩→肘→腕→髋）。 */
export const SKELETON_CONNECTIONS: ReadonlyArray<readonly [number, number]> = [
  [0, 1],
  [1, 2],
  [1, 3],
  [2, 4],
  [4, 6],
  [3, 5],
  [5, 7],
  [1, 8],
]

export function interpolatePose(
  start: PoseKeypoints,
  end: PoseKeypoints,
  t: number,
): PoseKeypoints {
  const clamped = Math.max(0, Math.min(1, t))
  const n = Math.min(start.length, end.length)
  const out: PoseKeypoints = []
  for (let i = 0; i < n; i += 1) {
    const a = start[i]
    const b = end[i]
    out.push({
      x: a.x + (b.x - a.x) * clamped,
      y: a.y + (b.y - a.y) * clamped,
    })
  }
  return out
}

export function parsePoseKeypoints(raw: unknown): PoseKeypoints | null {
  if (!Array.isArray(raw) || raw.length < 2) return null
  const pts: PoseKeypoints = []
  for (const item of raw) {
    if (!item || typeof item !== 'object') return null
    const x = (item as { x?: unknown }).x
    const y = (item as { y?: unknown }).y
    if (typeof x !== 'number' || typeof y !== 'number') return null
    if (!Number.isFinite(x) || !Number.isFinite(y)) return null
    pts.push({ x, y })
  }
  return pts
}
