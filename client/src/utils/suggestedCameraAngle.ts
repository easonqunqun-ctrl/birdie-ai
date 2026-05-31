import type { CameraAngle } from '@/types/api'
import type { DetectSwingsResponse } from '@/types/analysis'
import { CAMERA_ANGLE_LABEL } from '@/types/analysis'

export interface SuggestedCameraAngleResult {
  angle: CameraAngle
  /** 相对用户提交前所选机位是否被引擎改写 */
  changed: boolean
}

/** detect-swings 返回的建议机位；低置信 / null 时保持用户选择。 */
export function resolveSuggestedCameraAngle(
  current: CameraAngle,
  detected: Pick<DetectSwingsResponse, 'suggested_camera_angle'>,
): SuggestedCameraAngleResult {
  const suggested = detected.suggested_camera_angle
  if (suggested === 'face_on' || suggested === 'down_the_line') {
    return { angle: suggested, changed: suggested !== current }
  }
  return { angle: current, changed: false }
}

/** params 页短 toast：引擎改写机位时提示用户。 */
export function suggestedCameraAngleToastCopy(angle: CameraAngle): string {
  return `已根据画面识别为${CAMERA_ANGLE_LABEL[angle]}`
}
