/**
 * 视频首帧合规预检（W8-T5）
 *
 * 流程：
 *   1. 调用方传入 `thumbTempFilePath`（来自 Taro.chooseMedia 的 tempFiles[0].thumbTempFilePath）
 *   2. 通过 Taro.uploadFile 把首帧图 multipart 上传到 `POST /v1/security/media-check`
 *   3. 后端调微信 imgSecCheck；返回 `{ passed, reason? }`
 *
 * 调用方约定：
 *   - 返回 `{ passed: true }` → 继续后续上传视频
 *   - 返回 `{ passed: false, reason }` → toast + abort，不得继续上传
 *   - 本函数内部不 toast，由调用方统一处理（能确保报错位置可控）
 *
 * 为什么不走 request.ts：
 *   后端走 multipart/form-data，request.ts 统一包 JSON；这里单独起一个
 *   轻量 wrapper，与 analysisService.uploadToMinio 风格一致。
 */

import Taro from '@tarojs/taro'
import { storage } from '@/utils/storage'

declare const API_BASE_URL: string

export interface MediaCheckResult {
  passed: boolean
  reason?: string
}

/**
 * 上传视频首帧到后端做 imgSecCheck 合规预检。
 *
 * 网络错误 / 超时按 fail-open 处理（返回 `{ passed: true }`），
 * 避免合规服务临时故障把整个拍摄闭环卡死；后端日志会有明细。
 */
export async function checkVideoFirstFrame(
  thumbTempFilePath: string,
  scene: 'analysis' | 'share' = 'analysis',
): Promise<MediaCheckResult> {
  if (!thumbTempFilePath) {
    // 没有首帧可以检（RN 端未接入 / 部分设备缺失）→ 放行，等真审核再拦
    return { passed: true }
  }

  const baseURL = API_BASE_URL || 'http://localhost:8000/v1'
  const header: Record<string, string> = {}
  const token = storage.getToken()
  if (token) {
    header.Authorization = `Bearer ${token}`
  }

  return new Promise<MediaCheckResult>((resolve) => {
    Taro.uploadFile({
      url: `${baseURL}/security/media-check`,
      filePath: thumbTempFilePath,
      name: 'media',
      formData: { scene },
      header,
      success: (res) => {
        if (res.statusCode >= 500) {
          // 后端 5xx：fail open，别卡用户
          resolve({ passed: true, reason: '审核服务暂不可用' })
          return
        }
        try {
          const body = JSON.parse(res.data) as {
            code: number
            message: string
            data?: MediaCheckResult
          }
          if (body.code === 0 && body.data) {
            resolve(body.data)
          } else {
            // 4xx 业务错误（如 413 图片超限）→ 视为 fail open，不阻塞
            resolve({ passed: true, reason: body.message || '审核失败' })
          }
        } catch {
          resolve({ passed: true, reason: '审核响应解析失败' })
        }
      },
      fail: () => {
        resolve({ passed: true, reason: '审核服务网络异常' })
      },
    })
  })
}
