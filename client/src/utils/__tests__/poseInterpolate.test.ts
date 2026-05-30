import { interpolatePose } from '@/utils/poseInterpolate'

describe('poseInterpolate alias', () => {
  test('re-exports interpolatePose from posInterpolate', () => {
    const a = [{ x: 0, y: 0 }]
    const b = [{ x: 1, y: 1 }]
    expect(interpolatePose(a, b, 0.5)).toEqual([{ x: 0.5, y: 0.5 }])
  })
})
