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
/** Phase 2 灰度开关（编译期注入；正式包 .env.production 置 true） */
declare const PHASE2_PROFILE_V2_ENABLED: boolean
declare const PHASE2_COURSES_ENABLED: boolean
declare const PHASE2_PROS_ENABLED: boolean
declare const PHASE2_MEETUP_ENABLED: boolean
declare const PHASE2_COACH_ENABLED: boolean
declare const PHASE2_PUTTING_MODE_ENABLED: boolean
declare const PHASE2_CHIPPING_MODE_ENABLED: boolean
/** 逗号分隔的微信订阅消息模板 ID（编译期注入）；顺序见 `constants/subscribeTemplates.ts` */
declare const SUBSCRIBE_TEMPLATES: string
/** Taro 构建目标（weapp / h5 / rn …），与 `process.env.TARO_ENV` 等价但无 `process` */
declare const TARO_BUILD_TARGET: string
/** 微信开放平台移动 AppID（RN `registerApp`；小程序构建可为空字符串） */
declare const WECHAT_OPEN_APPID: string
/**
 * 启动日志水印：`<env>@<git-short-hash> built <UTC>`。
 * 由 client/config/index.ts 在 build 时通过 defineConstants 注入；
 * 业务代码请勿手写字符串，否则真机会再次出现"代码已更新但 marker 不变"的误导。
 */
declare const BUILD_MARKER: string

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
    TARO_APP_PHASE2_PROFILE_V2_ENABLED?: string
    TARO_APP_PHASE2_COURSES_ENABLED?: string
    TARO_APP_PHASE2_PROS_ENABLED?: string
    TARO_APP_PHASE2_MEETUP_ENABLED?: string
    TARO_APP_PHASE2_COACH_ENABLED?: string
    TARO_APP_PHASE2_PUTTING_MODE_ENABLED?: string
    TARO_APP_PHASE2_CHIPPING_MODE_ENABLED?: string
    /** RN 等直连 MinIO 预签名时使用；小程序默认走同源 `/analyses/uploads/...` */
    TARO_APP_ANALYSIS_DIRECT_MINIO?: string
  }
}
