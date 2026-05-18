/**
 * 微信一次性订阅消息模板 ID（微信公众平台申请后填入构建环境变量）。
 *
 * 取值来自 `config/index.ts::defineConstants.SUBSCRIBE_TEMPLATES`（即环境变量
 * `TARO_APP_SUBSCRIBE_TMPL_IDS`）：逗号分隔。**不得**在源码里读 `process.env`，否则
 * 懒加载分包在小程序里可能保留裸 `process`，运行时直接 `ReferenceError`.
 *
 * 约定顺序：第 1 个 = 分析完成提醒；第 2 个 = 会员已到期；第 3 个 = 会员即将到期（可选）。
 */

function envSubscribeTemplateId(raw: unknown): string {
  if (raw == null) return ''
  const s = String(raw).trim()
  if (!s || s === 'undefined' || s === 'null') return ''
  return s
}

function splitSubscribeTemplateIds(csv: string): string[] {
  return csv
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean)
}

const _SUBSCRIBE_IDS = splitSubscribeTemplateIds(SUBSCRIBE_TEMPLATES)

export const SUBSCRIBE_TPL_ANALYSIS_DONE = envSubscribeTemplateId(_SUBSCRIBE_IDS[0])

/** 会员到期提醒等（占位；与产品设计模板标题对齐后再启用） */
export const SUBSCRIBE_TPL_MEMBERSHIP_EXPIRE = envSubscribeTemplateId(_SUBSCRIBE_IDS[1])

/** 会员「即将到期」提醒（须配置第 3 个模板 ID；与 Celery 到期前 N 天任务一致） */
export const SUBSCRIBE_TPL_MEMBERSHIP_PRE_EXPIRE = envSubscribeTemplateId(_SUBSCRIBE_IDS[2])
