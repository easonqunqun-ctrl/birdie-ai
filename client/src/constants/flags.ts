/**
 * 客户端 feature flag 收口（W8-T3）
 *
 * 背景：
 *   `PAYMENT_ENABLED` / `PAYMENT_MOCK` / `PHASE2_*` 是 Taro 编译期常量
 *   （`config/index.ts::defineConstants` 注入），值在构建时已经定型。
 *   多处页面/组件直接 reference 全局常量虽然能工作，但散落各处不利于：
 *     - 统一加注释解释含义
 *     - 未来增加运行期判断（如灰度白名单 override）
 *
 *   本文件是这些 flag 的"收纳柜"：所有 UI 层面的"是否露出付费入口"
 *   的判断都从这里 import，避免每个页面自己 reference 全局常量。
 */

/**
 * 是否启用支付 UI 入口（升级会员按钮、配额耗尽开通会员 modal、profile
 * 会员中心入口等）。
 *
 * - W8 内测期 = `false`：所有付费入口对普通用户隐藏；白名单管理员可
 *   直接 `Taro.navigateTo('/pages/profile/membership')` + curl mock-pay
 * - W9 正式上线 = `true`：恢复全部付费 UI
 */
export const PAYMENT_ENABLED_FLAG: boolean = PAYMENT_ENABLED

/**
 * 编译期「默认联调用」开关（`TARO_APP_PAYMENT_MOCK !== 'false'` 时为 true）。
 *
 * ⚠️ **不得**用它来决定是否调用 `mockConfirm` vs `wx.requestPayment`——必须以
 * `POST /payments/orders` 返回的 `mock_mode` 为准，否则会与后端 `WECHAT_PAY_MOCK_MODE`
 * 不一致导致线上支付失败。
 *
 * 此处 flag 仅用于会员页底部提示文案等 UI；正式上线构建请设置 `TARO_APP_PAYMENT_MOCK=false`。
 */
export const PAYMENT_MOCK_FLAG: boolean = PAYMENT_MOCK

/**
 * P2-M9-02：装备清单 Tab + 画像 2.0 灰度开关。
 * 正式包：`TARO_APP_PHASE2_PROFILE_V2_ENABLED=true`（client/.env.production）。
 */
export const PHASE2_PROFILE_V2_ENABLED_FLAG: boolean = PHASE2_PROFILE_V2_ENABLED

/**
 * P2-M11-03 / M12-03 / M13：课程 / 球手库 / 约球灰度开关。
 * 与 backend `PHASE2_COURSES_ENABLED` / `PHASE2_PROS_ENABLED` /
 * `PHASE2_MEETUP_ENABLED` 双端联动。
 */
export const PHASE2_COURSES_ENABLED_FLAG: boolean = PHASE2_COURSES_ENABLED
export const PHASE2_PROS_ENABLED_FLAG: boolean = PHASE2_PROS_ENABLED
export const PHASE2_MEETUP_ENABLED_FLAG: boolean = PHASE2_MEETUP_ENABLED
export const PHASE2_COACH_ENABLED_FLAG: boolean = PHASE2_COACH_ENABLED
/** M10-01 推杆 mode UI + 引擎路由 */
export const PHASE2_PUTTING_MODE_ENABLED_FLAG: boolean = PHASE2_PUTTING_MODE_ENABLED
/** M10-02 切杆 mode UI */
export const PHASE2_CHIPPING_MODE_ENABLED_FLAG: boolean = PHASE2_CHIPPING_MODE_ENABLED
/** M10-03 yardage book */
export const PHASE2_YARDAGE_BOOK_ENABLED_FLAG: boolean = PHASE2_YARDAGE_BOOK_ENABLED
/** M10-05 训练计划 drill 类目匹配 */
export const PHASE2_TRAINING_CATEGORIES_ENABLED_FLAG: boolean =
  PHASE2_TRAINING_CATEGORIES_ENABLED
