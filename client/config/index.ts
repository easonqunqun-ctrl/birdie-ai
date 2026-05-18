import path from 'path'
import type { UserConfigExport } from '@tarojs/cli'

/** 打包进小程序的 API 根路径（须含 /v1）。空白会被视作「未配置」。 */
function resolveApiBaseUrl(): string {
  const raw = String(process.env.TARO_APP_API_BASE_URL ?? '').trim()
  const appEnv = String(process.env.TARO_APP_ENV ?? '').trim() || 'local'
  const fallbackLocal = 'http://localhost:8000/v1'

  if (!raw) {
    if (appEnv === 'production') {
      throw new Error(
        '[client/config] 体验版 / 正式包须在构建前配置 TARO_APP_API_BASE_URL（必须为 https://… 且含 /v1）。请编辑 client/.env.production 或 .env.production.local，勿留空（否则以前会静默退回 localhost，真机无法登录）。参见 docs/release-notes/go-live-weapp-fool-checklist.md',
      )
    }
    return fallbackLocal
  }

  if (appEnv === 'production') {
    const lower = raw.toLowerCase()
    if (!lower.startsWith('https://')) {
      throw new Error('[client/config] 正式构建 TARO_APP_API_BASE_URL 必须为 https')
    }
    if (lower.includes('localhost') || lower.includes('127.0.0.1')) {
      throw new Error('[client/config] 正式构建禁止使用 localhost / 127.0.0.1 作为 API 域名')
    }
  }

  return raw
}

const resolvedApiBaseUrl = resolveApiBaseUrl()

const config: UserConfigExport = {
  projectName: 'xiaoniao-ai',
  date: '2026-4-18',
  designWidth: 750,
  deviceRatio: {
    640: 2.34 / 2,
    750: 1,
    828: 1.81 / 2
  },
  sourceRoot: 'src',
  outputRoot: 'dist',
  plugins: [],
  defineConstants: {
    API_BASE_URL: JSON.stringify(resolvedApiBaseUrl),
    APP_ENV: JSON.stringify(process.env.TARO_APP_ENV || 'local'),
    // W7-T2：支付 mock 开关。默认 true，后端 `WECHAT_PAY_MOCK_MODE=true` 期间前端
    // 跳过 wx.requestPayment 改走 `mockConfirm`。W8 接真实商户号后设为 false。
    PAYMENT_MOCK: JSON.stringify(process.env.TARO_APP_PAYMENT_MOCK !== 'false'),
    // W8-T2 / T3：支付入口总开关（UI 层面）。
    // - 测试环境 / 内测：`false`，所有升级/会员入口隐藏，走 mock-pay 白名单通路。
    // - W9 正式上线：`true` 开启前端入口。
    // 默认 `false`，显式设置 `TARO_APP_PAYMENT_ENABLED=true` 才打开。
    PAYMENT_ENABLED: JSON.stringify(process.env.TARO_APP_PAYMENT_ENABLED === 'true'),
    /** 逗号分隔的订阅消息模板 ID；空则 `requestSubscribeMessage` 不调用 */
    SUBSCRIBE_TEMPLATES: JSON.stringify(process.env.TARO_APP_SUBSCRIBE_TMPL_IDS || ''),
    /** 顺序：1 分析完成 2 会员已到期 3 会员即将到期（到期前 N 天，与后端第三模板一致） */
    /** 供业务代码替代 `process.env.TARO_ENV`（懒加载 chunk 内 process 可能未注入） */
    TARO_BUILD_TARGET: JSON.stringify(process.env.TARO_ENV || ''),
    WECHAT_OPEN_APPID: JSON.stringify(process.env.TARO_APP_WECHAT_OPEN_APPID || ''),
  },
  copy: {
    patterns: [
      // W8-T2：tabBar 图标放 src/assets/tab/，构建时同步到小程序根。
      //   设计师 W9 上线前替换同名文件即可（不需要改 app.config.ts）。
      { from: 'src/assets/tab/', to: 'dist/assets/tab/' }
    ],
    options: {}
  },
  framework: 'react',
  compiler: 'webpack5',
  cache: {
    enable: true
  },
  alias: {
    '@': path.resolve(__dirname, '..', 'src'),
    '@components': path.resolve(__dirname, '..', 'src/components'),
    '@pages': path.resolve(__dirname, '..', 'src/pages'),
    '@services': path.resolve(__dirname, '..', 'src/services'),
    '@store': path.resolve(__dirname, '..', 'src/store'),
    '@utils': path.resolve(__dirname, '..', 'src/utils'),
    '@types': path.resolve(__dirname, '..', 'src/types')
  },
  mini: {
    /** weapp：勿解析 RN 依赖（内含 TS/RN 源码，会导致 webpack loader 报错） */
    webpackChain(chain: unknown) {
      if (process.env.TARO_ENV === 'weapp') {
        const c = chain as {
          resolve: { alias: { set: (k: string, v: string) => void } }
        }
        const stubDir = path.resolve(__dirname, '..', 'src/stubs')
        c.resolve.alias.set(
          'react-native-image-picker',
          path.join(stubDir, 'react-native-image-picker-weapp.js'),
        )
        c.resolve.alias.set('react-native-wechat-lib', path.join(stubDir, 'react-native-wechat-lib-weapp.js'))
        c.resolve.alias.set('react-native', path.join(stubDir, 'react-native-weapp.js'))
      }
    },
    postcss: {
      pxtransform: {
        enable: true,
        config: {}
      },
      url: {
        enable: true,
        config: {
          limit: 1024
        }
      },
      cssModules: {
        enable: false,
        config: {
          namingPattern: 'module',
          generateScopedName: '[name]__[local]___[hash:base64:5]'
        }
      }
    }
  },
  rn: {
    appName: 'xiaoniaoai',
    output: {
      iosSourceMapUrl: undefined,
      iosBundleOutput: undefined,
      iosAssetsDest: undefined,
      androidSourceMapUrl: undefined,
      androidBundleOutput: undefined,
      androidAssetsDest: undefined
    },
    postcss: {
      cssModules: {
        enable: false
      },
      /**
       * RN：sanitize 样式后交给 css-to-react-native（见 postcss-rn-sanitize.cjs）
       */
      './config/postcss-rn-sanitize.cjs': { enable: true },
    }
  },
  h5: {
    publicPath: '/',
    staticDirectory: 'static',
    postcss: {
      autoprefixer: {
        enable: true,
        config: {}
      },
      cssModules: {
        enable: false,
        config: {
          namingPattern: 'module',
          generateScopedName: '[name]__[local]___[hash:base64:5]'
        }
      }
    }
  }
}

export default function (merge: any) {
  const rn =
    process.env.TARO_ENV === 'rn'
      ? (require('./rn').default as Record<string, unknown>)
      : {}
  if (process.env.NODE_ENV === 'development') {
    return merge({}, config, rn, require('./dev').default)
  }
  return merge({}, config, rn, require('./prod').default)
}
