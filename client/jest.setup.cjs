/**
 * jest.setup.cjs
 *
 * 在 Jest 框架安装后、每个测试文件 import 业务代码前执行。
 *  - 注入 @testing-library/jest-dom matcher（toBeInTheDocument 等）
 *  - 给一些常用的全局 stub
 */

require('@testing-library/jest-dom')

// jsdom 没有 matchMedia；UI 组件偶尔会 query
if (typeof window !== 'undefined' && !window.matchMedia) {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: jest.fn().mockImplementation((query) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: jest.fn(),
      removeListener: jest.fn(),
      addEventListener: jest.fn(),
      removeEventListener: jest.fn(),
      dispatchEvent: jest.fn(),
    })),
  })
}

// jsdom 没有 ResizeObserver
if (typeof window !== 'undefined' && !window.ResizeObserver) {
  window.ResizeObserver = class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
}

// ============================================================
// 控制台噪声治理
// ============================================================
// 1) 业务代码 chatStore 留了大量 `[chat] ...` 调试日志（线上排查用），
//    测试触发错误分支时会把它们当成 console.error 一起打。这是预期行为，
//    不应当作测试失败/警告污染日志。这里 silence 掉 `[chat]` 前缀的日志，
//    其它仍正常透出，便于发现真实告警。
// 2) Taro 小程序 <Canvas canvasId="..."> 属性在 jsdom 下被 React 当成未知
//    DOM attribute 警告。我们的 stub 已经把 <Canvas> 渲成 <canvas>，但
//    业务 props canvasId 仍透传过去（线上小程序必需）。这里 silence。
const __origConsoleLog = console.log
const __origConsoleWarn = console.warn
const __origConsoleError = console.error

// 业务代码留下的运行期排查日志（线上需要、测试里 noise）
// 凡是 `[xxx:` / `[xxx]` 形如模块前缀的都视为业务日志，统一压掉
const __bizLogNoise =
  /^\s*\[(chat|userStore\.\w+|request:[a-z_]+|RadarChart|analysisStore|paymentStore|streamSSE)/i
// Taro 组件 stub 把 <Canvas> 等映射为 HTML <canvas>，但 props（canvasId、type='2d'、
// hoverClass 等）必须透传给小程序端，jsdom 下 React 一律告警未知 DOM prop。
// 这些都是预期，统一压掉。
const __reactUnknownPropNoise =
  /React does not recognize the .* prop on a DOM element|Unknown event handler property|Invalid (DOM property|value for prop)/
// 部分 React act() 警告在被 RTL 内部包裹时仍会出现，过滤"未包装的 state 更新"提示
const __reactActNoise = /not wrapped in act\(\.\.\.\)/

function __shouldSilence(args) {
  if (!args || args.length === 0) return false
  // React 的 console.error 走 format-string，告警文案在 args[1]；
  // chatStore 的 [chat] 业务日志直接在 args[0]。两者都拼起来匹配，避免漏检。
  let joined = ''
  for (let i = 0; i < Math.min(args.length, 3); i += 1) {
    const a = args[i]
    if (typeof a === 'string') {
      joined += a
      if (i < args.length - 1) joined += ' '
    }
  }
  if (!joined) return false
  if (__bizLogNoise.test(joined)) return true
  if (__reactUnknownPropNoise.test(joined)) return true
  if (__reactActNoise.test(joined)) return true
  return false
}

console.log = (...args) => {
  if (__shouldSilence(args)) return
  __origConsoleLog.apply(console, args)
}
console.warn = (...args) => {
  if (__shouldSilence(args)) return
  __origConsoleWarn.apply(console, args)
}
console.error = (...args) => {
  if (__shouldSilence(args)) return
  __origConsoleError.apply(console, args)
}
