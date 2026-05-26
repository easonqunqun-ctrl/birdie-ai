import type { AnalysisErrorInfo } from '@/types/analysis'

/**
 * 引擎侧错误码 → 用户可读文案
 *
 * - O-09：50100-50105 一期阻断错误
 * - P2-M7-03：50106-50123 细分错误码（docs/release-notes/p2-m7-03-error-codes-kickoff.md §3.1）
 * - 客户端 100% 覆盖 ERROR_REGISTRY；缺文案 CI 阻断（AC-2）
 */
export interface AnalysisFailureCopy {
  title: string
  message: string
  /** 可操作的拍摄/重试建议；系统级错误可为 null */
  hint: string | null
  /** 主 CTA 是否优先引导重拍（vs 稍后再试） */
  reshootRecommended: boolean
}

const ENGINE_FAILURE_COPY: Record<number, Omit<AnalysisFailureCopy, 'message'>> = {
  // ========== 一期保留段（50101-50105） ==========
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
  // ========== P2-M7-03 扩展段（50106-50123） ==========
  // 文案与 ai_engine/app/errors.py ERROR_REGISTRY 1:1 对齐
  50106: {
    title: '视频时长过短',
    hint: '挥杆视频至少拍 3 秒，请包含完整上杆到收杆后再上传。',
    reshootRecommended: true,
  },
  50107: {
    title: '视频时长过长',
    hint: '单段挥杆请控制在 30 秒以内，只拍一次挥杆动作即可。',
    reshootRecommended: true,
  },
  50108: {
    title: '视频分辨率过低',
    hint: '请在手机设置中选 1080p 及以上，并确保球员清晰占画面 1/2 以上。',
    reshootRecommended: true,
  },
  50109: {
    title: '光线不足',
    hint: '请在光线充足的练习场或户外重拍，避免逆光与强阴影。',
    reshootRecommended: true,
  },
  50110: {
    title: '画面抖动过大',
    hint: '请固定手机或使用三脚架，拍摄时避免手持晃动。',
    reshootRecommended: true,
  },
  50111: {
    title: '清晰度不稳定',
    hint: '拍摄时保持对焦清晰，避免半清晰半模糊；擦净镜头后重拍。',
    reshootRecommended: true,
  },
  50112: {
    title: '视频质量未达标',
    hint: '请改善光线、稳定机位并确保全身入镜后重新拍摄。',
    reshootRecommended: true,
  },
  50113: {
    title: '人物未完整入镜',
    hint: '请退后 2-3 米，确保头到脚完整出现在画面中再拍。',
    reshootRecommended: true,
  },
  50114: {
    title: '动作识别置信度偏低',
    hint: '请穿与背景对比明显的服装，避免遮挡，在简洁背景下重拍。',
    reshootRecommended: true,
  },
  50115: {
    title: '视频解码异常',
    hint: '请重新导出或另存视频后再上传；避免使用损坏的文件。',
    reshootRecommended: true,
  },
  50116: {
    title: '关键动作无法识别',
    hint: '请确保侧向或正对机位，球员不要被球包/他人遮挡。',
    reshootRecommended: true,
  },
  50117: {
    title: '视频方向异常',
    hint: '请在系统相机中关闭异常旋转，竖屏正常握持拍摄。',
    reshootRecommended: true,
  },
  50118: {
    title: '分析超时',
    hint: '请缩短视频时长或稍后重试；持续出现请联系客服。',
    reshootRecommended: false,
  },
  50119: {
    title: '服务繁忙',
    hint: '当前分析人数较多，请稍后再试。',
    reshootRecommended: false,
  },
  50120: {
    title: '视频格式暂不支持',
    hint: '请在相机设置中选「兼容性最佳」或 H.264 / mp4 格式后重拍。',
    reshootRecommended: true,
  },
  50121: {
    title: '慢动作格式无法识别',
    hint: '请用普通模式拍摄，或在相册中「转换为兼容格式」后再上传。',
    reshootRecommended: true,
  },
  50122: {
    title: '检测到多次挥杆',
    hint: '请每段视频只拍一次挥杆，或剪辑掉多余动作后再上传。',
    reshootRecommended: true,
  },
  50123: {
    title: '模式与球杆不匹配',
    hint: '推杆分析请选择推杆模式；全挥杆请勿选推杆。',
    reshootRecommended: true,
  },
}

/**
 * 已注册引擎错误码全表（与 ai_engine ERROR_REGISTRY 1:1 对齐）
 * 用于 CI 门禁单测：缺文案 PR 阻断（AC-2）
 */
export const REGISTERED_ENGINE_ERROR_CODES: readonly number[] = Object.freeze([
  50101, 50102, 50103, 50104, 50105,
  50106, 50107, 50108, 50109, 50110,
  50111, 50112, 50113, 50114, 50115,
  50116, 50117, 50118, 50119, 50120,
  50121, 50122, 50123,
])

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
