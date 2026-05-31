import type { CameraAngle } from '@/types/api'

/**
 * P2-M7-R1 · A8 机位能力声明（TrustBadge 下轻量条）。
 * ``rotation_reading_unreliable`` 文案见 ``QUALITY_WARNING_COPY``（与引擎 locale A6 对齐）。
 */
export function linesForMeasurabilityNotice(
  cameraAngle: CameraAngle | string | null | undefined,
  _qualityWarnings: string[] | null | undefined,
): string[] {
  if (cameraAngle === 'down_the_line') {
    return [
      '侧面机位：转肩角度、X-Factor 等旋转类指标无法从 2D 画面稳定测量，已自动跳过；请以下杆轨迹、节奏等可测维度为主。',
    ]
  }
  return []
}
