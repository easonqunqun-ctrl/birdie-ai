/**
 * W10：仅在 TARO_ENV=rn 时由 config/index.ts 合并进来（分离模式）。
 * - 宿主与 Pods：见同级 [`RN_SHELL.md`](../RN_SHELL.md)。
 * - 产物输出路径与官方文档示例一致：https://docs.taro.zone/docs/react-native
 * - appName 与官方壳默认 taroDemo 对齐；改名为 xiaoniaoai 需同步改壳工程 AppDelegate/MainActivity。
 */
import path from 'path'

const shellRoot = path.resolve(__dirname, '..', 'rn-shell')

export default {
  rn: {
    appName: 'taroDemo',
    output: {
      iosBundleOutput: path.join(shellRoot, 'ios', 'main.jsbundle'),
      iosAssetsDest: path.join(shellRoot, 'ios'),
      androidBundleOutput: path.join(shellRoot, 'android', 'app', 'src', 'main', 'assets', 'index.android.bundle'),
      androidAssetsDest: path.join(shellRoot, 'android', 'app', 'src', 'main', 'res'),
    },
  },
}
