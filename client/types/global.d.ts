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
 * W8-T2 / T3：支付入口 UI 总开关。
 *   false 时隐藏所有升级/会员入口；白名单账号仍可 curl 后端 mock-pay。
 *   W9 正式上线前置为 true。
 */
declare const PAYMENT_ENABLED: boolean
/** 逗号分隔的微信订阅消息模板 ID（编译期注入） */
declare const SUBSCRIBE_TEMPLATES: string
/** 微信开放平台移动 AppID（RN `registerApp`；小程序构建可为空字符串） */
declare const WECHAT_OPEN_APPID: string

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
    TARO_APP_PAYMENT_ENABLED?: string
    /** RN 等直连 MinIO 预签名时使用；小程序默认走同源 `/analyses/uploads/...` */
    TARO_APP_ANALYSIS_DIRECT_MINIO?: string
  }
}
