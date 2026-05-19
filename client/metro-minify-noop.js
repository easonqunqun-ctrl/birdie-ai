/**
 * Metro noop minifier
 *
 * metro 0.72 期望 minifier 模块导出形如：
 *   module.exports = function minify({ code, map, filename, reserved, config }) {
 *     return { code, map }
 *   }
 *
 * 这里不做任何压缩，原样返回。仅用于 CI bundle 门禁，详见 metro.config.js。
 *
 * 不在 jest collectCoverageFrom 范围内（位于 client/ 根目录，而非 src/）。
 */
module.exports = function noopMinify({ code, map }) {
  return { code, map }
}
