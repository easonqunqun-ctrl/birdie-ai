/**
 * jest.polyfills.cjs
 *
 * 在 Jest 安装框架到全局之前注入 polyfill。
 * 部分依赖（msw / undici / undici-types / web crypto）会在 import 时直接读
 * TextEncoder / TextDecoder / fetch，这些在 jsdom 默认环境里要么缺要么不全。
 */

const { TextEncoder, TextDecoder } = require('util')

if (typeof globalThis.TextEncoder === 'undefined') {
  globalThis.TextEncoder = TextEncoder
}
if (typeof globalThis.TextDecoder === 'undefined') {
  globalThis.TextDecoder = TextDecoder
}

// jsdom 没有 web streams API（ReadableStream），但部分模块（如 sseClient.ts
// 的 H5 路径）会用到。node 18+ 在 'stream/web' 里自带，挂到 globalThis 备用。
//
// 注意：测试里如果直接需要 `Response` / `fetch` / `ReadableStream` 等 web 标准
// API，最稳的做法是给那个文件加 `@jest-environment node`（node 18+ 全局自带
// undici 实现），见 src/utils/__tests__/sseClient.test.ts。这里只是兜底。
try {
  const webStreams = require('stream/web')
  if (typeof globalThis.ReadableStream === 'undefined' && webStreams.ReadableStream) {
    globalThis.ReadableStream = webStreams.ReadableStream
  }
} catch (_) {
  // node <18：跳过
}

// 部分代码读 process.env.TARO_ENV 来做端分叉；测试默认按 weapp 走
if (!process.env.TARO_ENV) {
  process.env.TARO_ENV = 'weapp'
}

// Taro `defineConstants` 在编译时把这些注入为全局 define（详见 client/types/global.d.ts）；
// jest 没有这层，业务代码裸名访问会抛 ReferenceError。
// 这里手动挂到 globalThis（在 jsdom 下等同 window），裸名查找会沿 scope chain 命中。
// 测试里如需切换分支：beforeEach 改写后调用 jest.resetModules() 再 import 业务模块。
if (typeof globalThis.API_BASE_URL === 'undefined') {
  globalThis.API_BASE_URL = 'http://localhost:8000/v1'
}
if (typeof globalThis.APP_ENV === 'undefined') {
  globalThis.APP_ENV = 'test'
}
if (typeof globalThis.PAYMENT_MOCK === 'undefined') {
  globalThis.PAYMENT_MOCK = true
}
if (typeof globalThis.PAYMENT_ENABLED === 'undefined') {
  globalThis.PAYMENT_ENABLED = false
}
if (typeof globalThis.PHASE2_PROFILE_V2_ENABLED === 'undefined') {
  globalThis.PHASE2_PROFILE_V2_ENABLED = false
}
if (typeof globalThis.PHASE2_COURSES_ENABLED === 'undefined') {
  globalThis.PHASE2_COURSES_ENABLED = false
}
if (typeof globalThis.PHASE2_PROS_ENABLED === 'undefined') {
  globalThis.PHASE2_PROS_ENABLED = false
}
if (typeof globalThis.PHASE2_MEETUP_ENABLED === 'undefined') {
  globalThis.PHASE2_MEETUP_ENABLED = false
}
if (typeof globalThis.PHASE2_COACH_ENABLED === 'undefined') {
  globalThis.PHASE2_COACH_ENABLED = false
}
if (typeof globalThis.SUBSCRIBE_TEMPLATES === 'undefined') {
  globalThis.SUBSCRIBE_TEMPLATES = ''
}
if (typeof globalThis.TARO_BUILD_TARGET === 'undefined') {
  globalThis.TARO_BUILD_TARGET = 'weapp'
}
if (typeof globalThis.WECHAT_OPEN_APPID === 'undefined') {
  globalThis.WECHAT_OPEN_APPID = ''
}
