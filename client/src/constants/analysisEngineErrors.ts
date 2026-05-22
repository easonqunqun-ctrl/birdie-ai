import type { AnalysisErrorInfo } from '@/types/analysis'

/** O-09：引擎侧阻断错误（50100-50105）→ 等待页/历史失败态用户文案 */
export interface AnalysisFailureCopy {
  title: string
  message: string
  /** 可操作的拍摄/重试建议；系统级错误可为 null */
  hint: string | null
  /** 主 CTA 是否优先引导重拍（vs 稍后再试） */
  reshootRecommended: boolean
}

const ENGINE_FAILURE_COPY: Record<number, Omit<AnalysisFailureCopy, 'message'>> = {
  50101: {
    title: '视频无法处理',
    hint: '请确认文件完整且为常见 MP4 格式后重新上传；若从相册导入，可先保存再选一次。',
    reshootRecommended: true,
  },
  50102: {
    title: '视频画质未达标',
    hint: '请在光线充足、侧向全身入镜处重拍；擦净镜头并保持机位稳定，避免过暗或严重模糊。',
    reshootRecommended: true,
  },
  50103: {
    title: '未检测到挥杆人物',
    hint: '请确保球员全身在画面中、镜头与挥杆方向呈约 90°，背景尽量简洁后再拍。',
    reshootRecommended: true,
  },
  50104: {
    title: '未识别到完整挥杆',
    hint: '视频需包含一次完整挥杆（上杆—击球—收杆）；请避免静止画面或仅走路等非挥杆动作。',
    reshootRecommended: true,
  },
  50105: {
    title: 'AI 引擎暂时不可用',
    hint: '这通常是服务端临时问题，请稍后再试；若多次出现请联系客服并提供错误码。',
    reshootRecommended: false,
  },
}

const TRANSPORT_FAILURE: Omit<AnalysisFailureCopy, 'message'> = {
  title: '分析服务连接失败',
  hint: '网络或服务暂时异常，请稍后再试；你的视频本身可能没有问题。',
  reshootRecommended: false,
}

const GENERIC_FAILURE: Omit<AnalysisFailureCopy, 'message'> = {
  title: '分析失败',
  hint: '请重新拍摄一次；若问题持续，请联系客服。',
  reshootRecommended: true,
}

/** 将 status.error 映射为等待页/历史页可展示文案；优先使用后端 message */
export function describeAnalysisFailure(
  error: AnalysisErrorInfo | null | undefined,
): AnalysisFailureCopy {
  if (!error) {
    return {
      ...GENERIC_FAILURE,
      message: '抱歉，这次分析没能完成，请重新拍摄一次。',
    }
  }

  const code = error.code
  const backendMessage = error.message?.trim()

  if (code === 50100) {
    return {
      ...TRANSPORT_FAILURE,
      message: backendMessage || '分析服务暂时不可用，请稍后再试。',
    }
  }

  const preset = ENGINE_FAILURE_COPY[code]
  if (preset) {
    return {
      ...preset,
      message: backendMessage || preset.title,
    }
  }

  return {
    ...GENERIC_FAILURE,
    message: backendMessage || '抱歉，这次分析没能完成，请重新拍摄一次。',
  }
}
