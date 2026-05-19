/**
 * Jest 配置（Taro 3 + React 18 + TS，端无关共享层）
 *
 * 设计原则：
 *  - 只覆盖 client/src/{services,utils,store,components,constants} 的端无关代码
 *  - pages/ 与 adapters/ 暂不纳入；adapters 的端分叉留给 W10 RN smoke
 *  - babel-jest（而非 ts-jest）：与 taro 自身用的 babel 编译保持一致语义
 *  - moduleNameMapper：把 @tarojs/* 替换为本地手写 stub；scss 走 identity-obj-proxy
 *  - jsdom 环境：RTL 组件渲染必需
 */
const path = require('path')

module.exports = {
  rootDir: __dirname,
  testEnvironment: 'jsdom',
  // 框架安装到全局环境之前：polyfill TextEncoder / fetch 等
  setupFiles: ['<rootDir>/jest.polyfills.cjs'],
  // 框架安装之后：注入 jest-dom matcher、统一 mock 桩
  setupFilesAfterEnv: ['<rootDir>/jest.setup.cjs'],
  testMatch: [
    '<rootDir>/src/**/__tests__/**/*.test.ts',
    '<rootDir>/src/**/__tests__/**/*.test.tsx',
  ],
  transform: {
    // babel-jest 的 configFile 不支持 <rootDir> 占位符（babel 直接当字面路径用），必须传绝对路径
    '^.+\\.(t|j)sx?$': [
      'babel-jest',
      { configFile: path.resolve(__dirname, 'babel.config.test.cjs') },
    ],
  },
  transformIgnorePatterns: [
    // Taro 与部分依赖发布 ESM；Jest 默认忽略 node_modules，下列例外走转译
    '/node_modules/(?!(@tarojs|@babel/runtime)/)',
  ],
  moduleNameMapper: {
    // 样式：所有 *.scss / *.css 走 identity-obj-proxy
    '\\.(scss|css)$': 'identity-obj-proxy',
    // Taro 组件 / 运行时：用本地 stub
    '^@tarojs/components$': '<rootDir>/src/__mocks__/tarojs-components.tsx',
    '^@tarojs/components-rn$': '<rootDir>/src/__mocks__/tarojs-components.tsx',
    '^@tarojs/taro$': '<rootDir>/src/__mocks__/tarojs.ts',
    '^@tarojs/taro-rn$': '<rootDir>/src/__mocks__/tarojs.ts',
    // 与 tsconfig.json paths 对齐
    '^@/(.*)$': '<rootDir>/src/$1',
    '^@components/(.*)$': '<rootDir>/src/components/$1',
    '^@services/(.*)$': '<rootDir>/src/services/$1',
    '^@store/(.*)$': '<rootDir>/src/store/$1',
    '^@utils/(.*)$': '<rootDir>/src/utils/$1',
    '^@types/(.*)$': '<rootDir>/src/types/$1',
  },
  moduleFileExtensions: ['ts', 'tsx', 'js', 'jsx', 'json'],
  collectCoverageFrom: [
    'src/services/**/*.{ts,tsx}',
    'src/utils/**/*.{ts,tsx}',
    'src/store/**/*.{ts,tsx}',
    'src/components/**/*.{ts,tsx}',
    'src/constants/**/*.{ts,tsx}',
    '!src/**/*.d.ts',
    '!src/**/__tests__/**',
    '!src/**/__mocks__/**',
    // RN 分叉文件由 W10 单独覆盖
    '!src/components/**/*.rn.{ts,tsx}',
  ],
  coverageThreshold: {
    /**
     * 阈值策略（W9 首批基线）：
     *  - 不按目录粗粒度卡（services/utils 里仍有大量未测文件：sseClient / track /
     *    videoQualityPrecheck / mediaCheck / trainingService，会把分母拉低，
     *    粗粒度阈值反而堵死「首批测一部分→渐进式补齐」的合理节奏）。
     *  - 改为「已测文件锁分数」+「全局兜底基线」双层：
     *      ① 单文件门禁（只针对当前已写测试的文件）：低于既有水位 = CI 红。
     *      ② 全局基线 ~15%：随团队继续补测试逐步上调，防止整体倒退。
     *
     * 下一批应优先补的目标（按 ROI 排序）：
     *   sseClient.ts（664 行，对话流式心脏） / track.ts（埋点） /
     *   videoQualityPrecheck.ts / mediaCheck.ts / chatStore 流式编排 / analysisService.uploadToMinio。
     */
    // 全局基线（防退化）：
    //   注意 Jest 29+ 的 `global` 阈值**只**针对没被 per-file/glob 阈值显式覆盖的
    //   剩余文件计算（未测的 mediaCheck / trainingService / drillLibrary 等），
    //   不是「整体覆盖率」。整体水位由 per-file 锁住（W9 末 ~68% lines）。
    //   global 这里取剩余文件的合理低基线即可：未测文件 ~10%，加 buffer 设 4%。
    global: { branches: 3, functions: 4, lines: 4, statements: 4 },

    // 已测文件锁水位（数值 = 当前实测 - 1~3%，留出 minor refactor 缓冲）
    './src/services/request.ts':         { branches: 65, functions: 90, lines: 85, statements: 80 },
    './src/services/paymentService.ts':  { branches: 90, functions: 100, lines: 100, statements: 100 },
    './src/services/userService.ts':     { branches: 90, functions: 100, lines: 100, statements: 100 },
    './src/services/chatService.ts':     { branches: 45, functions: 55, lines: 50, statements: 50 },
    './src/services/analysisService.ts': { branches: 65, functions: 85, lines: 85, statements: 85 },
    './src/services/mediaCheck.ts':        { branches: 80, functions: 100, lines: 95, statements: 95 },
    './src/services/shareService.ts':    { branches: 100, functions: 100, lines: 100, statements: 100 },
    './src/services/trainingService.ts': { branches: 0, functions: 100, lines: 100, statements: 100 },
    './src/services/invitationService.ts': { branches: 100, functions: 100, lines: 100, statements: 100 },
    './src/utils/storage.ts':            { branches: 95, functions: 90, lines: 95, statements: 95 },
    './src/utils/privacy.ts':            { branches: 88, functions: 85, lines: 95, statements: 95 },
    './src/utils/sdkVersion.ts':         { branches: 85, functions: 100, lines: 95, statements: 95 },
    './src/utils/tabNav.ts':             { branches: 95, functions: 100, lines: 95, statements: 95 },
    './src/utils/wxDomainMessages.ts':   { branches: 90, functions: 100, lines: 95, statements: 95 },
    './src/utils/sseClient.ts':          { branches: 40, functions: 50, lines: 48, statements: 45 },
    './src/utils/track.ts':              { branches: 75, functions: 95, lines: 95, statements: 90 },
    './src/utils/videoQualityPrecheck.ts': { branches: 85, functions: 100, lines: 95, statements: 95 },
    './src/store/analysisStore.ts':      { branches: 95, functions: 100, lines: 95, statements: 95 },
    './src/store/userStore.ts':          { branches: 85, functions: 100, lines: 95, statements: 95 },
    './src/store/chatStore.ts':          { branches: 78, functions: 95, lines: 88, statements: 88 },
  },
  clearMocks: true,
  restoreMocks: true,
  testTimeout: 10000,
}
