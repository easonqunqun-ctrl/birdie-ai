/**
 * 跨端支付 adapter（微信小程序虚拟支付 + JSAPI）
 */

import Taro from '@tarojs/taro'
import type { PrepayParams } from '@/types/payment'

type VirtualPaymentResult = {
  errMsg?: string
  errCode?: number
}

declare module '@tarojs/taro' {
  interface TaroStatic {
    requestVirtualPayment?: (opts: {
      signData: string
      paySig: string
      signature: string
      mode: string
      success?: (res: VirtualPaymentResult) => void
      fail?: (res: VirtualPaymentResult) => void
    }) => Promise<VirtualPaymentResult>
  }
}

export async function requestWechatPayment(prepay: PrepayParams): Promise<void> {
  if (prepay.payment_method === 'virtual') {
    await requestVirtualPayment(prepay)
    return
  }
  await requestJsapiPayment(prepay)
}

async function requestVirtualPayment(prepay: PrepayParams): Promise<void> {
  if (!prepay.sign_data || !prepay.pay_sig || !prepay.signature || !prepay.mode) {
    throw new Error('虚拟支付参数不完整')
  }
  const fn = Taro.requestVirtualPayment
  if (typeof fn !== 'function') {
    throw new Error('当前微信版本不支持虚拟支付，请升级微信客户端')
  }
  await new Promise<void>((resolve, reject) => {
    fn.call(Taro, {
      signData: prepay.sign_data!,
      paySig: prepay.pay_sig!,
      signature: prepay.signature!,
      mode: prepay.mode!,
      success: () => resolve(),
      fail: (res) => {
        const msg = res?.errMsg || 'requestVirtualPayment:fail'
        reject(Object.assign(new Error(msg), { errMsg: msg, errCode: res?.errCode }))
      },
    })
  })
}

async function requestJsapiPayment(prepay: PrepayParams): Promise<void> {
  if (!prepay.time_stamp || !prepay.nonce_str || !prepay.package || !prepay.pay_sign) {
    throw new Error('支付参数异常')
  }
  await Taro.requestPayment({
    timeStamp: prepay.time_stamp,
    nonceStr: prepay.nonce_str,
    package: prepay.package,
    signType: (prepay.sign_type || 'RSA') as 'RSA',
    paySign: prepay.pay_sign,
  })
}
