/**
 * 客户端 feature flag 收口（W8-T3）
 *
 * 背景：
 *   `PAYMENT_ENABLED` / `PAYMENT_MOCK` 是 Taro 编译期常量
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
 *
 * - 默认 `false`：profile 页"我的装备"入口隐藏，API 端 404（与 backend
 *   `PHASE2_PROFILE_V2_ENABLED` 同步开关）
 * - 启用：W22 把此常量翻 `true` + 后端切 `PHASE2_PROFILE_V2_ENABLED=true` 同步上线
 *
 * 与 backend `settings.PHASE2_PROFILE_V2_ENABLED` 双端联动，避免出现"客户端有
 * 入口但 API 404"的尴尬。
 *
 * 后续可通过 `defineConstants` 注入编译期常量替换硬编码（参考
 * `PAYMENT_ENABLED_FLAG` 模式），W22 灰度时再做。
 */
export const PHASE2_PROFILE_V2_ENABLED_FLAG: boolean = false

/**
<<<<<<< HEAD
 * P2-M12-03：球手对比库灰度开关。
 *
 * 与 backend `settings.PHASE2_PROS_ENABLED` 同步：
 * - 默认 `false`：球手列表 / 详情页 onShow 即退回
 * - 启用：W22+ 与后端同时切 true
 */
export const PHASE2_PROS_ENABLED_FLAG: boolean = false
=======
 * P2-M11-03：课程学习路径灰度开关。
 *
 * 与 backend `settings.PHASE2_COURSES_ENABLED` 同步：
 * - 默认 `false`：训练 Tab 内的"学习路径"入口隐藏；直跳 `/pages/courses/index`
 *   也无法看到列表（后端 404）
 * - 启用：W22+ 与后端 `PHASE2_COURSES_ENABLED=true` 同步上线
 *
 * 与 `PHASE2_PROFILE_V2_ENABLED_FLAG` 完全独立，两个能力可以分批灰度。
 */
export const PHASE2_COURSES_ENABLED_FLAG: boolean = false
>>>>>>> origin/main
