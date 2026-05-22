/**
 * O-08 / O-09 客户端硬预检阻断码 → 用户可读文案。
 * 与 `videoQualityPrecheck.ts` 阻断阈值对齐；引擎侧仍由 50102 等兜底。
 */
export const QUALITY_BLOCK_COPY: Record<string, string> = {
  too_dark: '画面过暗，AI 无法稳定识别挥杆。请在光线充足、侧向全身入镜处重拍。',
  too_blurry: '画面过于模糊，暂无法开始分析。请擦净镜头并在光线充足处重拍。',
  too_shaky: '画面抖动过大，暂无法分析。请固定机位或使用三脚架后重拍。',
}

export function linesForQualityBlocks(codes: string[] | null | undefined): string[] {
  if (!codes?.length) return []
  const lines: string[] = []
  for (const code of codes) {
    const c = String(code).trim()
    if (!c) continue
    lines.push(QUALITY_BLOCK_COPY[c] ?? `拍摄质量未达标（${c}），请改善后重拍。`)
  }
  return lines
}
