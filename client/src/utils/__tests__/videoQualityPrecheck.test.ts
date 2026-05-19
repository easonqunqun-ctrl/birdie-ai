/**
 * @jest-environment node
 *
 * videoQualityPrecheck 单测（纯算法，跑 node 更快）
 *
 * 关注的不变式：
 *  - 阈值常量与 `ai_engine/app/pipeline/preprocess.py` 同源；改了一定要同步
 *  - 暗光 / 抖动 / 模糊 三类启发式信号最终要折成 quality_warnings 机器码
 *  - 与后端 qualityWarnings.ts / preprocess._scan_quality 对齐
 */

import {
  CLIENT_PRECHECK_THRESHOLDS,
  downscaleRgbaToGray,
  earlyShakeSamplePositionsSec,
  grayFromRgbaFrame,
  meanAbsDiffGray,
  mergeQualityWarningCodes,
  metricsFromRgba,
  stabilityScoreFromGrayFrames,
  stabilityScoreFromMeanDiff,
  warningCodesFromStabilityScore,
  warningCodesFromThumbMetrics,
} from '@/utils/videoQualityPrecheck'

describe('warningCodesFromThumbMetrics · 暗光判定', () => {
  test('明亮 + 清晰 → 无 warning', () => {
    expect(
      warningCodesFromThumbMetrics({ meanLuminance: 140, laplacianVariance: 200 }),
    ).toEqual([])
  })

  test('亮度低于阈值 → low_light', () => {
    expect(
      warningCodesFromThumbMetrics({
        meanLuminance: CLIENT_PRECHECK_THRESHOLDS.MEAN_LUMINANCE_LOW_LIGHT - 1,
        laplacianVariance: 200,
      }),
    ).toEqual(['low_light'])
  })

  test('刚好等于阈值不算暗（边界保留偏明亮一侧）', () => {
    expect(
      warningCodesFromThumbMetrics({
        meanLuminance: CLIENT_PRECHECK_THRESHOLDS.MEAN_LUMINANCE_LOW_LIGHT,
        laplacianVariance: 200,
      }),
    ).toEqual([])
  })

  test('亮度偏低 + 拉普拉斯方差很小 → 仍判 low_light（夜间糊）', () => {
    expect(
      warningCodesFromThumbMetrics({
        meanLuminance: 100, // > 阈值 78，但 < 110
        laplacianVariance: CLIENT_PRECHECK_THRESHOLDS.LAPLACIAN_VAR_VERY_BLURRY - 1,
      }),
    ).toEqual(['low_light'])
  })

  test('亮度 >= 110 时即使方差很小也不报 low_light（白天对焦糊不是暗光）', () => {
    expect(
      warningCodesFromThumbMetrics({ meanLuminance: 120, laplacianVariance: 10 }),
    ).toEqual([])
  })
})

describe('stabilityScoreFromMeanDiff · 与 preprocess._scan_quality 公式一致', () => {
  test('mean_diff = 0（完全不动）→ 1.0 最稳', () => {
    expect(stabilityScoreFromMeanDiff(0)).toBe(1)
  })

  test('mean_diff = scale 上限 → 0 最不稳', () => {
    expect(stabilityScoreFromMeanDiff(CLIENT_PRECHECK_THRESHOLDS.STABILITY_MEAN_DIFF_SCALE)).toBe(0)
  })

  test('超过 scale 仍 clamp 到 0', () => {
    expect(stabilityScoreFromMeanDiff(CLIENT_PRECHECK_THRESHOLDS.STABILITY_MEAN_DIFF_SCALE * 2)).toBe(0)
  })

  test('mean_diff = scale/2 → 0.5', () => {
    expect(
      stabilityScoreFromMeanDiff(CLIENT_PRECHECK_THRESHOLDS.STABILITY_MEAN_DIFF_SCALE / 2),
    ).toBe(0.5)
  })
})

describe('warningCodesFromStabilityScore', () => {
  test('稳像分 < 阈值 → camera_shake', () => {
    expect(
      warningCodesFromStabilityScore(
        CLIENT_PRECHECK_THRESHOLDS.STABILITY_SCORE_CAMERA_SHAKE - 0.01,
      ),
    ).toEqual(['camera_shake'])
  })

  test('稳像分 >= 阈值 → 空', () => {
    expect(
      warningCodesFromStabilityScore(CLIENT_PRECHECK_THRESHOLDS.STABILITY_SCORE_CAMERA_SHAKE),
    ).toEqual([])
    expect(warningCodesFromStabilityScore(0.95)).toEqual([])
  })
})

describe('mergeQualityWarningCodes · 去重保留首次出现顺序', () => {
  test('多组合并去重', () => {
    expect(
      mergeQualityWarningCodes(['low_light', 'camera_shake'], ['camera_shake', 'blur'], ['low_light']),
    ).toEqual(['low_light', 'camera_shake', 'blur'])
  })

  test('全空 → []', () => {
    expect(mergeQualityWarningCodes()).toEqual([])
    expect(mergeQualityWarningCodes([], [], [])).toEqual([])
  })
})

describe('earlyShakeSamplePositionsSec', () => {
  test('正常时长 → 4 个均匀采样点，最大不超过 1.2s 或 22% 时长', () => {
    const positions = earlyShakeSamplePositionsSec(3) // 3s 视频
    expect(positions).toHaveLength(4)
    expect(positions[0]).toBe(0)
    expect(positions[positions.length - 1]).toBeCloseTo(Math.min(1.2, 3 * 0.22))
    // 应该单调递增
    for (let i = 1; i < positions.length; i += 1) {
      expect(positions[i]).toBeGreaterThan(positions[i - 1])
    }
  })

  test('超短视频（< 0.5s）按 0.5s 兜底', () => {
    const positions = earlyShakeSamplePositionsSec(0.2)
    expect(positions[positions.length - 1]).toBeCloseTo(Math.min(1.2, 0.5 * 0.22))
  })

  test('长视频末点不超过 1.2s（避免采到挥杆中段）', () => {
    const positions = earlyShakeSamplePositionsSec(60)
    expect(positions[positions.length - 1]).toBeCloseTo(1.2)
  })
})

describe('downscaleRgbaToGray + meanAbsDiffGray · 数值正确性', () => {
  test('全黑 4x4 → 全 0 灰度', () => {
    const black = new Uint8ClampedArray(4 * 4 * 4) // 全 0
    const gray = downscaleRgbaToGray(black, 4, 4, 2, 2)
    expect(Array.from(gray)).toEqual([0, 0, 0, 0])
  })

  test('全白 4x4 → 全 255 灰度（容差 1e-3）', () => {
    const white = new Uint8ClampedArray(4 * 4 * 4).fill(255)
    // alpha 也是 255，不影响（公式不读 alpha）
    const gray = downscaleRgbaToGray(white, 4, 4, 2, 2)
    for (const v of gray) {
      // 0.299+0.587+0.114 = 1.0 * 255
      expect(v).toBeCloseTo(255, 3)
    }
  })

  test('meanAbsDiffGray：相同帧 → 0；不同帧 → 平均绝对差', () => {
    const a = new Float32Array([10, 20, 30, 40])
    const b = new Float32Array([10, 20, 30, 40])
    expect(meanAbsDiffGray(a, b)).toBe(0)
    const c = new Float32Array([11, 22, 33, 44])
    // diffs = [1,2,3,4]，mean = 2.5
    expect(meanAbsDiffGray(a, c)).toBe(2.5)
  })

  test('meanAbsDiffGray：空数组 → 0', () => {
    expect(meanAbsDiffGray(new Float32Array(0), new Float32Array(0))).toBe(0)
  })
})

describe('stabilityScoreFromGrayFrames', () => {
  test('< 2 帧 → null', () => {
    expect(stabilityScoreFromGrayFrames([new Float32Array([1, 2])])).toBeNull()
    expect(stabilityScoreFromGrayFrames([])).toBeNull()
  })

  test('两帧完全相同 → 1.0 最稳', () => {
    const f1 = new Float32Array([10, 20, 30])
    const f2 = new Float32Array([10, 20, 30])
    expect(stabilityScoreFromGrayFrames([f1, f2])).toBe(1)
  })

  test('两帧大幅变化（mean_diff > scale）→ 0', () => {
    const f1 = new Float32Array(64).fill(0)
    const f2 = new Float32Array(64).fill(255) // mean_diff = 255 > 30
    expect(stabilityScoreFromGrayFrames([f1, f2])).toBe(0)
  })
})

describe('grayFromRgbaFrame · 自动 downscale 到 SHAKE_SAMPLE_MAX_SIDE', () => {
  test('小图（< 64 边长）保留原始尺寸', () => {
    // 单像素白：[255,255,255,255]
    const rgba = new Uint8ClampedArray([255, 255, 255, 255])
    const gray = grayFromRgbaFrame(rgba, 1, 1)
    // grayFromRgbaFrame 内部 max(8, round(1 * 1)) = 8 → 8x8
    expect(gray.length).toBe(8 * 8)
  })

  test('大图（>=64 边长）downscale 后总像素数 <= 64*64', () => {
    const w = 640
    const h = 480
    const rgba = new Uint8ClampedArray(w * h * 4)
    const gray = grayFromRgbaFrame(rgba, w, h)
    expect(gray.length).toBeLessThanOrEqual(64 * 64)
    // 长边按 64 scale = 64/640 = 0.1 → 短边 480*0.1=48 → 64*48 = 3072
    expect(gray.length).toBe(64 * 48)
  })
})

describe('metricsFromRgba', () => {
  test('空图 → 默认值（避免后续公式 NaN）', () => {
    const empty = new Uint8ClampedArray(0)
    expect(metricsFromRgba(empty, 0, 0)).toEqual({
      meanLuminance: 128,
      laplacianVariance: 200,
    })
  })

  test('全黑 → 亮度 0 / 方差 0', () => {
    const w = 8
    const h = 8
    const black = new Uint8ClampedArray(w * h * 4)
    const m = metricsFromRgba(black, w, h)
    expect(m.meanLuminance).toBe(0)
    expect(m.laplacianVariance).toBe(0)
  })

  test('全白 → 亮度 255 / 方差 0', () => {
    const w = 8
    const h = 8
    const white = new Uint8ClampedArray(w * h * 4).fill(255)
    const m = metricsFromRgba(white, w, h)
    expect(m.meanLuminance).toBeCloseTo(255, 3)
    expect(m.laplacianVariance).toBeCloseTo(0, 3)
  })

  test('棋盘 → 高方差（明显边缘）', () => {
    const w = 8
    const h = 8
    const rgba = new Uint8ClampedArray(w * h * 4)
    for (let y = 0; y < h; y += 1) {
      for (let x = 0; x < w; x += 1) {
        const v = (x + y) % 2 === 0 ? 255 : 0
        const o = (y * w + x) * 4
        rgba[o] = v
        rgba[o + 1] = v
        rgba[o + 2] = v
        rgba[o + 3] = 255
      }
    }
    const m = metricsFromRgba(rgba, w, h)
    expect(m.laplacianVariance).toBeGreaterThan(0)
    expect(m.meanLuminance).toBeCloseTo(127.5, 0)
  })
})
