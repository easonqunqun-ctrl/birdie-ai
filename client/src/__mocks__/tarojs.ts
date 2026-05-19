/**
 * @tarojs/taro 测试 stub
 *
 * 真实 @tarojs/taro 在 jest 里直接 import 会触发 Taro 自身的 runtime
 * 初始化（依赖小程序 / RN 平台 API），与 jsdom 不兼容。这里只暴露
 * 业务代码用到的方法，全部用 jest.fn 实现，便于测试里 .mockResolvedValue。
 *
 * 用法（在测试里）：
 *   import Taro from '@tarojs/taro'
 *   ;(Taro.request as jest.Mock).mockResolvedValue({ statusCode: 200, data: { code: 0 } })
 */

type AnyFn = (...args: any[]) => any

const noop = () => undefined
const noopAsync = () => Promise.resolve(undefined)

const storageMap = new Map<string, unknown>()

export const __resetTaroMock = () => {
  storageMap.clear()
  for (const k of Object.keys(Taro)) {
    const v = (Taro as Record<string, unknown>)[k]
    if (typeof v === 'function' && 'mockReset' in (v as object)) {
      ;(v as jest.Mock).mockReset()
    }
  }
}

const Taro = {
  // ===== 网络 =====
  request: jest.fn(),
  uploadFile: jest.fn(() => ({
    onProgressUpdate: jest.fn(),
    abort: jest.fn(),
  })),
  downloadFile: jest.fn(),

  // ===== 路由 =====
  navigateTo: jest.fn(noopAsync),
  redirectTo: jest.fn(noopAsync),
  reLaunch: jest.fn(noopAsync),
  switchTab: jest.fn(noopAsync),
  navigateBack: jest.fn(noopAsync),

  // ===== UI =====
  showToast: jest.fn(noopAsync),
  hideToast: jest.fn(noop),
  showLoading: jest.fn(noopAsync),
  hideLoading: jest.fn(noop),
  showModal: jest.fn(() => Promise.resolve({ confirm: true, cancel: false })),
  showActionSheet: jest.fn(noopAsync),

  // ===== 存储（用内存 Map 模拟）=====
  setStorageSync: jest.fn((k: string, v: unknown) => storageMap.set(k, v)),
  getStorageSync: jest.fn((k: string) => (storageMap.has(k) ? storageMap.get(k) : '')),
  removeStorageSync: jest.fn((k: string) => storageMap.delete(k)),
  clearStorageSync: jest.fn(() => storageMap.clear()),
  setStorage: jest.fn(({ key, data }: { key: string; data: unknown }) => {
    storageMap.set(key, data)
    return Promise.resolve()
  }),
  getStorage: jest.fn(({ key }: { key: string }) =>
    Promise.resolve({ data: storageMap.get(key) ?? null }),
  ),
  removeStorage: jest.fn(({ key }: { key: string }) => {
    storageMap.delete(key)
    return Promise.resolve()
  }),

  // ===== 媒体 / 拍摄 =====
  chooseMedia: jest.fn(),
  chooseVideo: jest.fn(),
  getImageInfo: jest.fn(),
  createOffscreenCanvas: jest.fn(),
  getVideoInfo: jest.fn(),

  // ===== 系统 =====
  getSystemInfoSync: jest.fn(() => ({
    platform: 'devtools',
    SDKVersion: '3.0.0',
    statusBarHeight: 20,
    windowWidth: 375,
    windowHeight: 667,
    screenWidth: 375,
    screenHeight: 812,
    safeArea: { top: 44, bottom: 778, left: 0, right: 375, width: 375, height: 734 },
  })),
  getEnv: jest.fn(() => 'WEAPP'),
  ENV_TYPE: { WEAPP: 'WEAPP', RN: 'RN' },

  // ===== 登录 / 支付 / 订阅消息 =====
  login: jest.fn(() => Promise.resolve({ code: 'mock_login_code', errMsg: 'login:ok' })),
  requestPayment: jest.fn(noopAsync),
  requestSubscribeMessage: jest.fn(noopAsync),
  getUserProfile: jest.fn(),
  getSetting: jest.fn(() => Promise.resolve({ authSetting: {} })),

  // ===== 触觉反馈 =====
  vibrateShort: jest.fn(noopAsync),
  vibrateLong: jest.fn(noopAsync),

  // ===== 事件流 / 引用 =====
  eventCenter: {
    on: jest.fn(),
    off: jest.fn(),
    trigger: jest.fn(),
  },
  getCurrentInstance: jest.fn(() => ({
    router: { params: {} },
    page: {},
  })),

  // ===== 选择器 / Canvas =====
  createSelectorQuery: jest.fn(() => {
    const chain: any = {
      select: jest.fn(() => chain),
      selectAll: jest.fn(() => chain),
      fields: jest.fn(() => chain),
      boundingClientRect: jest.fn(() => chain),
      scrollOffset: jest.fn(() => chain),
      // 默认 exec 回 [{ node: null, width: 0, height: 0 }]，让组件走"取不到"分支
      exec: jest.fn((cb: (r: unknown[]) => void) => {
        cb([{ node: null, width: 0, height: 0 }])
      }),
    }
    return chain
  }),
  getWindowInfo: jest.fn(() => ({ pixelRatio: 2, windowWidth: 375, windowHeight: 667 })),

  // ===== Taro hooks =====
  // 测试里组件可调用 (Taro.useReady as jest.Mock).mockImplementation(cb => cb()) 强制触发
  useReady: jest.fn(),
  useDidShow: jest.fn(),
  useDidHide: jest.fn(),
  useRouter: jest.fn(() => ({ params: {} })),
  useLoad: jest.fn(),
  useShareAppMessage: jest.fn(),

  // ===== 占位（业务代码 typeof 检查后才调用，这里不实现也不会炸）=====
  arrayBufferToBase64: jest.fn((b: ArrayBuffer) => Buffer.from(b).toString('base64')),
  base64ToArrayBuffer: jest.fn((s: string) => Uint8Array.from(Buffer.from(s, 'base64')).buffer),
} as unknown as Record<string, AnyFn> & {
  ENV_TYPE: { WEAPP: string; RN: string }
  eventCenter: Record<string, AnyFn>
}

// Named exports：组件常用 `import { useReady, useDidShow, useRouter } from '@tarojs/taro'`
// 这些必须显式从 default 桩里再次导出，babel-jest 不会自动桥接。
export const useReady = Taro.useReady
export const useDidShow = Taro.useDidShow
export const useDidHide = Taro.useDidHide
export const useRouter = Taro.useRouter
export const useLoad = Taro.useLoad
export const useShareAppMessage = Taro.useShareAppMessage
export const eventCenter = Taro.eventCenter
export const ENV_TYPE = Taro.ENV_TYPE
export const getCurrentInstance = Taro.getCurrentInstance

export default Taro
