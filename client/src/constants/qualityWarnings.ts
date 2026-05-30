/**
 * AI 引擎非阻断质量提示（quality_warnings machine codes）→ 用户可读文案。
 * 与 `ai_engine/app/pipeline/preprocess.py::quality_warnings_from_preprocess` 对齐。
 */
export const QUALITY_WARNING_COPY: Record<string, string> = {
  low_light: '光线偏暗，关键点检测可能不够稳。建议在光线充足处侧向全身拍摄后重试。',
  camera_shake: '画面抖动略大，可能影响追踪精度。建议固定机位或使用三脚架后再拍。',
  partial_occlusion: '部分时段身体关键点被遮挡，追踪可能不完整。请确保侧向全身入镜、避免他人或物体遮挡。',
  low_pose_confidence: '姿态关键点置信度偏低，分数可能波动。建议在光线充足、背景简洁处重拍。',
  angle_limited_scoring:
    '当前机位下部分维度（如转肩角度）无法从 2D 画面稳定测量，系统已自动调整计分方式；建议同机位多拍几次看趋势。',
  rotation_reading_unreliable:
    '旋转类读数波动较大（常见于侧面转播/慢动作），相关诊断已降权，请以可测维度为主。',
  score_low_trust:
    '本次视频的可测维度偏少或关键点不够稳，总分已保守处理；建议在规范机位、光线充足处重拍后再对比。',
}

/** O-10：软警告存在时报告页统一脚注（docs/01 §4.4） */
export const QUALITY_WARNING_IMPACT_FOOTNOTE =
  '以上问题未阻断分析，但结果可能受影响。建议在光线充足、机位稳定处重拍以获得更准确的分数。'

export function linesForQualityWarnings(codes: string[] | null | undefined): string[] {
  if (!codes?.length) return []
  const lines: string[] = []
  for (const code of codes) {
    const c = String(code).trim()
    if (!c) continue
    lines.push(QUALITY_WARNING_COPY[c] ?? `本次分析检测到「${c}」，若结果波动可尝试改善光线与机位后重拍。`)
  }
  return lines
}
