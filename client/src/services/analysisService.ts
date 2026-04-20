/**
 * 挥杆分析相关接口封装。
 *
 * 所有方法都会走 `./request.ts` 的统一错误处理；uploadToMinio 例外，因为它打的是
 * MinIO / COS 直连 URL（非后端），不走统一包装，错误由本层单独翻译。
 */

import Taro from '@tarojs/taro'
import type {
  AnalysisListResponse,
  AnalysisReportResponse,
  AnalysisStatusResponse,
  CreateAnalysisRequest,
  CreateAnalysisResponse,
  UploadTokenRequest,
  UploadTokenResponse,
} from '@/types/analysis'
import { http } from './request'

export interface UploadProgressEvent {
  progress: number // 0-100
  totalBytesSent: number
  totalBytesExpectedToSend: number
}

export interface UploadToMinioOptions {
  onProgress?: (e: UploadProgressEvent) => void
}

export const analysisService = {
  /** 申请上传凭证：后端预扣配额前会在这里先做语义校验 */
  getUploadToken(payload: UploadTokenRequest) {
    return http.post<UploadTokenResponse>('/analyses/upload-token', payload)
  },

  /**
   * 直传到 MinIO / COS。
   *
   * 约定：
   * - 上传成功 = HTTP 204（S3 协议）或 200（某些网关会改写）
   * - 其它 HTTP 码都当失败，把 `body` 原样放进 Error.message 供排查
   *
   * 注意：Taro.uploadFile 在小程序平台由 `wx.uploadFile` 实现，formData 里的 key 值
   * 必须是字符串；前端拿到的 `fields` 也全是字符串，直接原样塞入即可。
   */
  uploadToMinio(
    filePath: string,
    token: UploadTokenResponse,
    opts: UploadToMinioOptions = {},
  ): Promise<void> {
    return new Promise<void>((resolve, reject) => {
      const task = Taro.uploadFile({
        url: token.upload_url,
        filePath,
        name: 'file',
        formData: { ...token.fields },
        success: (res) => {
          const code = res.statusCode
          if (code === 204 || code === 200) {
            resolve()
          } else {
            const msg = `上传失败（HTTP ${code}）${res.data ? `：${truncate(res.data, 160)}` : ''}`
            reject(new Error(msg))
          }
        },
        fail: (err) => {
          reject(new Error(err.errMsg || '上传失败，请检查网络'))
        },
      })
      if (opts.onProgress && typeof task?.progress === 'function') {
        task.progress((e) => {
          opts.onProgress?.({
            progress: e.progress,
            totalBytesSent: e.totalBytesSent,
            totalBytesExpectedToSend: e.totalBytesExpectedToSend,
          })
        })
      }
    })
  },

  createAnalysis(payload: CreateAnalysisRequest) {
    return http.post<CreateAnalysisResponse>('/analyses', payload)
  },

  getStatus(analysisId: string) {
    return http.get<AnalysisStatusResponse>(`/analyses/${analysisId}/status`, {
      // 轮询时不弹 toast；失败由调用方决定降级策略
      silent: true,
    })
  },

  /**
   * 获取报告。
   *
   * 特殊约定：id = 'sample' 会路由到 `/analyses/sample`（免配额 / 免登、返回固定的
   * 示例数据），用于 MVP §3.6 "用示例视频先体验一下"。前端报告页可用同一个入口
   * 渲染，无需分支 UI。
   */
  getReport(analysisId: string) {
    if (analysisId === 'sample') {
      return http.get<AnalysisReportResponse>('/analyses/sample')
    }
    return http.get<AnalysisReportResponse>(`/analyses/${analysisId}`)
  },

  listAnalyses(params: { page?: number; page_size?: number; club_type?: string } = {}) {
    const query = new URLSearchParams()
    if (params.page) query.set('page', String(params.page))
    if (params.page_size) query.set('page_size', String(params.page_size))
    if (params.club_type) query.set('club_type', params.club_type)
    const qs = query.toString()
    return http.get<AnalysisListResponse>(`/analyses${qs ? `?${qs}` : ''}`)
  },
}

function truncate(s: unknown, max: number): string {
  const str = typeof s === 'string' ? s : JSON.stringify(s)
  return str.length > max ? `${str.slice(0, max)}...` : str
}
