import Taro from '@tarojs/taro'
import { precheckVideoQuality } from '@/adapters/videoQualityPrecheck'
import { linesForQualityWarnings } from '@/constants/qualityWarnings'

/**
 * 若有警告则弹窗；用户选「仍要继续」返回 true，选「重新拍摄」返回 false。
 */
export async function confirmQualityWarningsIfNeeded(
  warningCodes: string[],
): Promise<boolean> {
  if (!warningCodes.length) return true

  const lines = linesForQualityWarnings(warningCodes)
  const content = lines.join('\n\n')

  const { confirm } = await Taro.showModal({
    title: '拍摄质量提示',
    content: `${content}\n\n结果可能受影响，建议改善光线与机位后重拍。是否仍要继续上传？`,
    confirmText: '仍要继续',
    cancelText: '重新拍摄',
  })
  return confirm
}

export { precheckVideoQuality }
