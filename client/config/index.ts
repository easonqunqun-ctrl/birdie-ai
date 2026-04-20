import path from 'path'
import type { UserConfigExport } from '@tarojs/cli'

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
    API_BASE_URL: JSON.stringify(process.env.TARO_APP_API_BASE_URL || 'http://localhost:8000/v1'),
    APP_ENV: JSON.stringify(process.env.TARO_APP_ENV || 'local')
  },
  copy: {
    patterns: [],
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
      }
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
  if (process.env.NODE_ENV === 'development') {
    return merge({}, config, require('./dev').default)
  }
  return merge({}, config, require('./prod').default)
}
