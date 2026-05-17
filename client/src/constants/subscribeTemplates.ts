/**
 * 微信一次性订阅消息模板 ID（微信公众平台申请后填入构建环境变量）。
 * 为空则跳过 `requestSubscribeMessage`，开发/未过审模板时不报错。
 */
export const SUBSCRIBE_TPL_ANALYSIS_DONE =
  (process.env.TARO_APP_SUBSCRIBE_TPL_ANALYSIS_DONE || '').trim()

/** 会员到期提醒等（占位；与产品设计模板标题对齐后再启用） */
export const SUBSCRIBE_TPL_MEMBERSHIP_EXPIRE =
  (process.env.TARO_APP_SUBSCRIBE_TPL_MEMBERSHIP_EXPIRE || '').trim()
