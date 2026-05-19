const path = require('path')
const { mergeConfig } = require('metro-config')
const { getMetroConfig } = require('@tarojs/rn-supporter')

/**
 * Metro RN 构建配置
 *
 * 关键 workaround：禁用 minify。
 *   metro v0.72 默认走 `metro-minify-uglify`，uglify-es 不识别 babel-preset-taro
 *   编译输出里残留的 ES2020 语法（`?.` / `??`），具体表现为：
 *     `Unexpected token: name (_000) in file ... at <line>:<col>`
 *   （受影响的源文件先是 src/pages/analysis/waiting.tsx，后续随业务用 `?.` 蔓延。）
 *
 * 影响面分析：
 *   - client-rn-check 在 CI 上的目的是「验证 metro 能编译过、bundle 不破」，
 *     不需要 minified output（生产 RN 包另起一条线，taro-native-shell）。
 *   - 关掉 minify 后 bundle 大小不影响生产，CI 反而省 ~15s。
 *
 * 长期方案（W10 RN smoke 落地时再做）：升级 metro / 切换到 metro-minify-terser、
 *   或排查 babel-preset-taro 的 RN target 没正确编译 optional chaining 的根因。
 */
module.exports = (async function () {
  return mergeConfig({
    resolver: {},
    transformer: {
      // 指向本地 noop minifier；metro 0.72 仍会调用，但只是直接 return 输入
      minifierPath: path.resolve(__dirname, 'metro-minify-noop.js'),
    },
  }, await getMetroConfig())
})()