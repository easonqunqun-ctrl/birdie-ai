import {
  interpolatePose,
  parsePoseKeypoints,
  type PoseKeypoints,
} from '@/utils/posInterpolate'

const A: PoseKeypoints = [
  { x: 0, y: 0 },
  { x: 1, y: 0 },
]
const B: PoseKeypoints = [
  { x: 10, y: 0 },
  { x: 10, y: 10 },
]

describe('posInterpolate', () => {
  test('interpolatePose t=0 returns start', () => {
    expect(interpolatePose(A, B, 0)).toEqual(A)
  })

  test('interpolatePose t=1 returns end', () => {
    expect(interpolatePose(A, B, 1)).toEqual(B)
  })

  test('interpolatePose t=0.5 is midpoint', () => {
    const mid = interpolatePose(A, B, 0.5)
    expect(mid[0]).toEqual({ x: 5, y: 0 })
    expect(mid[1]).toEqual({ x: 5.5, y: 5 })
  })

  test('interpolatePose clamps t', () => {
    expect(interpolatePose(A, B, -1)[0].x).toBe(0)
    expect(interpolatePose(A, B, 2)[0].x).toBe(10)
  })

  test('parsePoseKeypoints accepts valid array', () => {
    expect(
      parsePoseKeypoints([
        { x: 0.5, y: 0.2 },
        { x: 0.6, y: 0.3 },
      ]),
    ).toEqual([
      { x: 0.5, y: 0.2 },
      { x: 0.6, y: 0.3 },
    ])
  })

  test('parsePoseKeypoints rejects invalid', () => {
    expect(parsePoseKeypoints(null)).toBeNull()
    expect(parsePoseKeypoints([{ x: 'bad', y: 1 }])).toBeNull()
  })
})
