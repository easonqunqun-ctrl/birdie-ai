/**
 * 微信小程序手机号授权 adapter（M13-09 约球实名）。
 */

import { ensurePrivacyAuthorized, PrivacyDeniedError } from '@/utils/privacy'

export class PhoneAuthError extends Error {
  readonly code: 'denied' | 'unavailable'

  constructor(code: 'denied' | 'unavailable', message: string) {
    super(message)
    this.name = 'PhoneAuthError'
    this.code = code
  }
}

type GetPhoneNumberDetail = {
  code?: string
  errMsg?: string
}

/** 从 Button `getPhoneNumber` 事件提取 code；用户拒绝时抛 PhoneAuthError。 */
export async function extractPhoneCodeFromEvent(
  detail: GetPhoneNumberDetail | undefined,
): Promise<string> {
  if (process.env.TARO_ENV !== 'weapp') {
    throw new PhoneAuthError('unavailable', '当前环境不支持手机号授权')
  }

  try {
    await ensurePrivacyAuthorized('getPhoneNumber')
  } catch (e) {
    if (e instanceof PrivacyDeniedError) {
      throw new PhoneAuthError('denied', '需同意隐私协议后才能授权手机号')
    }
    throw e
  }

  const errMsg = detail?.errMsg ?? ''
  if (/deny|cancel|fail/i.test(errMsg) && !detail?.code) {
    throw new PhoneAuthError('denied', '未授权微信手机号')
  }

  const code = detail?.code?.trim()
  if (!code) {
    throw new PhoneAuthError('unavailable', '未获取到手机号凭证，请重试')
  }
  return code
}
