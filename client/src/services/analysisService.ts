/**
 * 挥杆分析相关接口封装。
 *
 * 视频上报默认走 **`POST /v1/analyses/uploads/{upload_id}/video`**（与 API 同源），
 * 避免小程序直连 MinIO 预签名 POST 在网关/模拟器上出现 502、timeout。
 * `upload-token` 仍返回 `upload_url` / `fields`：服务端未上线同源上传时会自动回退为预签名直传。
 */

import Taro from '@tarojs/taro'
import type {
  AnalysisListResponse,
  AnalysisReportResponse,
  AnalysisStatusResponse,
  CreateAnalysisRequest,
  CreateAnalysisResponse,
  DetectSwingsResponse,
  UploadTokenRequest,
  UploadTokenResponse,
} from '@/types/analysis'
import { storage } from '@/utils/storage'
import { http } from './request'

export interface UploadProgressEvent {
  progress: number // 0-100
  totalBytesSent: number
  totalBytesExpectedToSend: number
}

export interface UploadToMinioOptions {
  onProgress?: (e: UploadProgressEvent) => void
}

/** 分析链路弱网 / 冷启动：默认 wx.request 仅 15s，凭证与创建任务易被误判超时 */
const ANALYSIS_API_TIMEOUT_MS = 120000
/** 视频直传 MinIO（经 HTTPS）；显式超时避免开发者工具或低端机沿用保守默认值 */
const DIRECT_UPLOAD_TIMEOUT_MS = 300000
/** MVP W8·E1：网关 5xx / 弱网可有限重试；401/403/404/业务码不重试同款凭证 */
const UPLOAD_MAX_ATTEMPTS = 3
const UPLOAD_RETRY_BACKOFF_MS = [0, 800, 2400]

function sleepMs(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

/**
 * 预签名或策略过期：`uploadFile` 返回 403/HTML /XML 中带 ExpiredSignature 时常态。
 * 此时应 **`upload-token` 重新拉凭证**再传，不得在客户端盲重刷同一表单。
 */
export function uploadLikelyNeedsFreshToken(message: string): boolean {
  const m = (message || '').trim()
  if (!m) return false
  return (
    /\b403\b/i.test(m) ||
    /Forbidden/i.test(m) ||
    /AccessDenied/i.test(m) ||
    /ExpiredToken|ExpiredSignature|RequestExpired|signature we calculated/i.test(m)
  )
}

function uploadNetworkLayerRetriable(message: string): boolean {
  const m = (message || '').trim()
  if (!m) return false
  if (/\b401\b/i.test(m) || /登录已过期/.test(m)) return false
  if (uploadLikelyNeedsFreshToken(m)) return false
  if (/HTTP\s*404\b/i.test(m)) return false
  if (/上传响应格式错误/.test(m)) return false
  if (/HTTP\s*(502|503|504)\b/i.test(m)) return true
  if (/网关无法连接|存储网关暂时不可用|502 Bad Gateway/i.test(m)) return true
  if (/超时|timed?\s*out|time\s*-?out/i.test(m)) return true
  if (/fail\b.*connect|ECONNRESET|ECONNREFUSED/i.test(m)) return true
  return /^上传失败，请检查网络$/i.test(m) || /^uploadFile:fail\b/i.test(m)
}

async function withUploadRetries(run: () => Promise<void>): Promise<void> {
  let lastErr: Error | undefined
  for (let i = 0; i < UPLOAD_MAX_ATTEMPTS; i += 1) {
    await sleepMs(UPLOAD_RETRY_BACKOFF_MS[i] ?? 800 * i)
    try {
      // eslint-disable-next-line no-await-in-loop
      await run()
      return
    } catch (e) {
      const err = e instanceof Error ? e : new Error(String(e))
      lastErr = err
      const retry = uploadNetworkLayerRetriable(err.message) && i < UPLOAD_MAX_ATTEMPTS - 1
      if (!retry) {
        throw err
      }
    }
  }
  throw lastErr ?? new Error('上传失败')
}

export const analysisService = {
  /** 申请上传凭证：后端预扣配额前会在这里先做语义校验 */
  getUploadToken(payload: UploadTokenRequest) {
    return http.post<UploadTokenResponse>('/analyses/upload-token', payload, {
      timeout: ANALYSIS_API_TIMEOUT_MS,
    })
  },

  /**
   * 上报视频：默认 **同源 API** multipart `file`，与 JWT 域名一致（微信小程序推荐）。
   *
   * 若 `TARO_APP_ANALYSIS_DIRECT_MINIO === 'true'`（如 RN 调试直传），则改走
   * `upload_url` + `fields` 预签名 POST。
   */
  uploadToMinio(
    filePath: string,
    token: UploadTokenResponse,
    opts: UploadToMinioOptions = {},
  ): Promise<void> {
    const directMinio =
      typeof process !== 'undefined' &&
      process.env?.TARO_APP_ANALYSIS_DIRECT_MINIO === 'true'
    if (directMinio) {
      return withUploadRetries(() =>
        uploadToMinioPresignedAttempt(filePath, token, opts),
      )
    }
    // 同源上传依赖服务端路由 POST /v1/analyses/uploads/{id}/video；旧镜像未合并时会 404。
    return withUploadRetries(() =>
      uploadVideoViaApiAttempt(filePath, token, opts),
    ).catch(async (err: unknown) => {
      const msg = err instanceof Error ? err.message : String(err)
      if (/HTTP\s*404\b/i.test(msg)) {
        return withUploadRetries(() => uploadToMinioPresignedAttempt(filePath, token, opts))
      }
      throw err instanceof Error ? err : new Error(msg)
    })
  },

  createAnalysis(payload: CreateAnalysisRequest) {
    return http.post<CreateAnalysisResponse>('/analyses', payload, {
      timeout: ANALYSIS_API_TIMEOUT_MS,
      /** params 页会自行 modal 提示，避免与本层 toast 重复 */
      silent: true,
    })
  },

  /** M7-13：上传后探测多挥候选（仅 full_swing；不扣配额） */
  detectSwings(uploadId: string) {
    return http.post<DetectSwingsResponse>(
      `/analyses/uploads/${encodeURIComponent(uploadId)}/detect-swings`,
      {},
      {
        timeout: ANALYSIS_API_TIMEOUT_MS,
        silent: true,
      },
    )
  },

  getStatus(analysisId: string) {
    return http.get<AnalysisStatusResponse>(`/analyses/${analysisId}/status`, {
      // 轮询时不弹 toast；失败由调用方决定降级策略
      silent: true,
      // 默认 wx.request 仅 15s，弱网或网关排队易被误判超时 → 与上传/创任务链路对齐
      timeout: ANALYSIS_API_TIMEOUT_MS,
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
      return http.get<AnalysisReportResponse>('/analyses/sample', {
        timeout: ANALYSIS_API_TIMEOUT_MS,
      })
    }
    return http.get<AnalysisReportResponse>(`/analyses/${analysisId}`, {
      timeout: ANALYSIS_API_TIMEOUT_MS,
    })
  },

  listAnalyses(params: { page?: number; page_size?: number; club_type?: string } = {}) {
    const query = new URLSearchParams()
    if (params.page) query.set('page', String(params.page))
    if (params.page_size) query.set('page_size', String(params.page_size))
    if (params.club_type) query.set('club_type', params.club_type)
    const qs = query.toString()
    return http.get<AnalysisListResponse>(`/analyses${qs ? `?${qs}` : ''}`)
  },

  /** 用户侧软删除：进行中不可删；示例不入库无需调用 */
  deleteAnalysis(analysisId: string) {
    return http.del(`/analyses/${analysisId}`)
  },

  /** 分享物料：小程序码 PNG（服务端落 COS/MinIO） */
  createShareCard(analysisId: string) {
    return http.post<{ wxa_code_url: string }>(
      `/analyses/${analysisId}/share-card`,
      {},
      { silent: true },
    )
  },
}

function uploadVideoViaApiAttempt(
  filePath: string,
  token: UploadTokenResponse,
  opts: UploadToMinioOptions,
): Promise<void> {
  const trimmed = typeof API_BASE_URL === 'string' ? API_BASE_URL.trim() : ''
  if (!trimmed) {
    return Promise.reject(new Error('API 地址未配置'))
  }
  const base = trimmed.replace(/\/$/, '')
  const url = `${base}/analyses/uploads/${token.upload_id}/video`
  const header: Record<string, string> = {}
  const tk = storage.getToken()
  if (tk) header.Authorization = `Bearer ${tk}`

  return new Promise<void>((resolve, reject) => {
    const task = Taro.uploadFile({
      url,
      filePath,
      name: 'file',
      header,
      timeout: DIRECT_UPLOAD_TIMEOUT_MS,
      success: (res) => {
        const sc = res.statusCode
        const raw = typeof res.data === 'string' ? res.data : ''
        if (sc === 401) {
          reject(new Error('登录已过期，请重新登录'))
          return
        }
        if (sc !== 200) {
          reject(new Error(formatDirectUploadError(sc, raw)))
          return
        }
        try {
          const body = JSON.parse(raw || '{}') as {
            code?: number
            message?: string
          }
          if (body.code !== 0) {
            reject(new Error(body.message || '上传失败'))
            return
          }
          resolve()
        } catch {
          reject(new Error('上传响应格式错误'))
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
}

/** 直连 MinIO/COS 预签名 POST（单 attempt；外层 `withUploadRetries`） */
function uploadToMinioPresignedAttempt(
  filePath: string,
  token: UploadTokenResponse,
  opts: UploadToMinioOptions,
): Promise<void> {
  return new Promise<void>((resolve, reject) => {
    const task = Taro.uploadFile({
      url: token.upload_url,
      filePath,
      name: 'file',
      formData: { ...token.fields },
      timeout: DIRECT_UPLOAD_TIMEOUT_MS,
      success: (res) => {
        const code = res.statusCode
        if (code === 204 || code === 200) {
          resolve()
        } else {
          const raw = typeof res.data === 'string' ? res.data : ''
          const msg = formatDirectUploadError(code, raw)
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
}

function truncate(s: unknown, max: number): string {
  const str = typeof s === 'string' ? s : JSON.stringify(s)
  return str.length > max ? `${str.slice(0, max)}...` : str
}

/** 直传存储失败：502 常为 Nginx 连不上 MinIO，别把整页 HTML 糊给用户 */
function formatDirectUploadError(statusCode: number, body: string): string {
  const snippet = truncate(body, 160)
  if (statusCode === 404) {
    return (
      `上传失败（HTTP 404）：服务端可能没有最新「同源上传」接口，请升级后端或检查 API 地址是否含 /v1`
    )
  }
  if (statusCode === 502 || statusCode === 503 || statusCode === 504) {
    const looksLikeNginx502 =
      /<title>\s*502\s+Bad\s+Gateway\s*<\/title>/i.test(body) ||
      /502 Bad Gateway/i.test(body)
    if (looksLikeNginx502 || statusCode === 504) {
      return (
        `上传失败（HTTP ${statusCode}）：网关无法连接到对象存储（MinIO）。` +
        '请在后端检查 MinIO 容器是否运行，以及网关是否把 `/minio/` 正确反向代理到 MinIO（端口一般为 9000）。'
      )
    }
    return `上传失败（HTTP ${statusCode}）：存储网关暂时不可用，请稍后重试`
  }
  return `上传失败（HTTP ${statusCode}）${snippet ? `：${snippet}` : ''}`
}
