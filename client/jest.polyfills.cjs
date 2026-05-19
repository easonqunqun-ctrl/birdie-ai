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
if (typeof globalThis.SUBSCRIBE_TEMPLATES === 'undefined') {
  globalThis.SUBSCRIBE_TEMPLATES = ''
}
if (typeof globalThis.TARO_BUILD_TARGET === 'undefined') {
  globalThis.TARO_BUILD_TARGET = 'weapp'
}
if (typeof globalThis.WECHAT_OPEN_APPID === 'undefined') {
  globalThis.WECHAT_OPEN_APPID = ''
}
