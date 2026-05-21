import type { VideoQualityPrecheckResult } from '@/utils/videoQualityPrecheck'

export type { VideoQualityPrecheckResult } from '@/utils/videoQualityPrecheck'

/**
 * 上传前质量预检（O-08 子集）—— **仅 RN/H5 fallback**。
 *
 * 端分叉机制：Taro 编译 weapp 时优先解析 `videoQualityPrecheck.weapp.ts` 覆盖本文件；
 * 也就是说本 base 文件**仅在 RN / H5 / 测试环境**被打包。weapp 真实实现在 `.weapp.ts`。
 *
 * 历史教训：本文件曾按 `process.env.TARO_ENV === 'weapp'` 内嵌 dynamic import 调
 * `.weapp.ts`，但因为 weapp 编译根本不打包本文件 → dynamic import 在 weapp 端是死代码；
 * 同时 `.weapp.ts` 当时只暴露 `precheckVideoQualityWeapp` 没暴露同名 `precheckVideoQuality`
 * 别名 → 调用方 import 拿到 undefined → 「开始分析」按钮静默失败。
 *
 * 现在的约定：本文件只负责 RN/H5 stub；`.weapp.ts` 自带 `precheckVideoQuality` 别名 export。
 */
export async function precheckVideoQuality(_input: {
  thumbTempFilePath?: string
  videoTempFilePath?: string
  durationSec?: number
}): Promise<VideoQualityPrecheckResult> {
  return { warnings: [], skipped: true, reason: 'unsupported_platform' }
}
