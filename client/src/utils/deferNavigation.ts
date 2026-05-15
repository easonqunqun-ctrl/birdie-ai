import Taro from '@tarojs/taro'

/** 最小延迟（ms），让首帧 setData 落稳后再导航 */
const FALLBACK_NAV_DELAY_MS = 24

/**
 * 延后触发 reLaunch，减轻小程序（尤其开发者工具 + lazyCodeLoading）首帧竞态：
 * 「Cannot read property 'addListener' of undefined」「Expected updated data…」等噪声日志。
 */
export function deferReLaunch(url: string): void {
  const go = () => {
    void Taro.reLaunch({ url })
  }
  const schedule = () => setTimeout(go, FALLBACK_NAV_DELAY_MS)
  if (typeof Taro.nextTick === 'function') {
    Taro.nextTick(schedule)
  } else {
    schedule()
  }
}
