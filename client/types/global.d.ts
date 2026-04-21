/// <reference types="@tarojs/taro" />

declare module '*.png'
declare module '*.gif'
declare module '*.jpg'
declare module '*.jpeg'
declare module '*.svg'
declare module '*.css'
declare module '*.less'
declare module '*.scss'
declare module '*.sass'
declare module '*.styl'

declare const API_BASE_URL: string
declare const APP_ENV: string
/** W7-T2：支付 mock 开关；默认 true，W8 接真实商户号后设为 false */
declare const PAYMENT_MOCK: boolean

/**
 * 微信小程序全局对象；Taro 类型定义默认不注入 `wx`（走 Taro.xxx 封装），
 * 但对话页的 SSE 实现需要用 `wx.canIUse` / `wx.request.enableChunked` 这些
 * Taro 还没透出的能力，所以用 any 放一个全局声明，避免每个引用点都写 declare。
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
declare const wx: any

declare namespace NodeJS {
  interface ProcessEnv {
    /** Taro 编译期环境变量 */
    TARO_ENV: 'weapp' | 'swan' | 'alipay' | 'h5' | 'rn' | 'tt' | 'qq' | 'jd'
    /** 自定义环境变量（来自 .env 或 cli --env） */
    TARO_APP_API_BASE_URL?: string
    TARO_APP_ENV?: string
    TARO_APP_PAYMENT_MOCK?: string
  }
}
