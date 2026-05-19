/**
 * 测试专用 babel 配置：babel-jest 用它编译 .ts/.tsx
 *
 * 与 babel.config.js（taro 编译用）解耦：taro preset 会注入小程序运行时
 * 相关的 plugin，会跟 jsdom 测试环境冲突；这里只走 env/react/typescript 三件套。
 */
module.exports = {
  presets: [
    [
      '@babel/preset-env',
      {
        // Node 环境跑测试：targets current node
        targets: { node: 'current' },
        // CommonJS：与 jest 默认 transform 一致
        modules: 'commonjs',
      },
    ],
    ['@babel/preset-react', { runtime: 'automatic' }],
    '@babel/preset-typescript',
  ],
}
