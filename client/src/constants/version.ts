/**
 * 客户端版本号常量。
 *
 * 维护方式：与 `client/package.json` 的 `version` 字段保持手动一致；
 * 升级正式版前在 PR 里同步修改两处（无构建时注入是为了避免
 * `require('../../package.json')` 把整个 package.json 打进小程序包）。
 */
export const CLIENT_VERSION = '1.2.45'
