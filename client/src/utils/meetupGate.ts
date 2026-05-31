/**
 * M13-09 · 约球合规错误码与跳转引导。
 */

import Taro from '@tarojs/taro'
import { isRequestError } from '@/services/request'

export const MEETUP_ERROR_MINOR = 40332
export const MEETUP_ERROR_IDENTITY = 40333
export const MEETUP_ERROR_TOS = 40334

export type MeetupGateAction = 'identity' | 'minor' | 'tos' | null

export function getMeetupErrorCode(error: unknown): number | undefined {
  if (isRequestError(error) && typeof error.code === 'number') {
    return error.code
  }
  return undefined
}

export function resolveMeetupGateAction(error: unknown): MeetupGateAction {
  const code = getMeetupErrorCode(error)
  if (code === MEETUP_ERROR_IDENTITY) return 'identity'
  if (code === MEETUP_ERROR_MINOR) return 'minor'
  if (code === MEETUP_ERROR_TOS) return 'tos'
  return null
}

export function buildMeetupIdentityVerifyUrl(redirect?: string): string {
  const base = '/pages/meetup/identity-verify'
  if (!redirect?.trim()) return base
  return `${base}?redirect=${encodeURIComponent(redirect.trim())}`
}

export function navigateToMeetupIdentityVerify(redirect?: string): void {
  void Taro.navigateTo({ url: buildMeetupIdentityVerifyUrl(redirect) })
}

export async function showMeetupMinorBlockedModal(): Promise<void> {
  await Taro.showModal({
    title: '暂不可用',
    content: '约球及相关功能仅向年满 14 周岁的用户开放。',
    showCancel: false,
    confirmText: '我知道了',
  })
}

/** 按 M13 错误码 toast / 跳转；返回 true 表示已处理。 */
export async function handleMeetupGateError(
  error: unknown,
  options?: { redirect?: string; onTosRequired?: () => void },
): Promise<boolean> {
  const action = resolveMeetupGateAction(error)
  if (action === 'identity') {
    navigateToMeetupIdentityVerify(options?.redirect)
    return true
  }
  if (action === 'minor') {
    await showMeetupMinorBlockedModal()
    return true
  }
  if (action === 'tos') {
    options?.onTosRequired?.()
    return true
  }
  return false
}
