import { Component, PropsWithChildren } from 'react'
import Taro from '@tarojs/taro'
import EnvBadge from '@/components/EnvBadge'
import { storage } from '@/utils/storage'
import { checkMinSdkVersion } from '@/utils/sdkVersion'
import { deferReLaunch } from '@/utils/deferNavigation'
import { flushTrack, track, trackError } from '@/utils/track'
import './app.scss'

declare const API_BASE_URL: string

class App extends Component<PropsWithChildren> {
  componentDidMount() {
    console.log(
      '%c[BUILD-MARKER]',
      'color:#062;font-weight:bold',
      'dist@2026-05-18 waiting-lg+spin report-no-delbtn | 若非此串请：`cd client && pnpm dev:weapp` 后预览，或用「详情→清缓存」',
    )

    if (TARO_BUILD_TARGET === 'weapp' && typeof API_BASE_URL === 'string') {
      const u = API_BASE_URL.trim().toLowerCase()
      const hits: string[] = []
      if (u.includes('test.example.com')) hits.push('test.example.com')
      if (u.includes('localhost') || u.includes('127.0.0.1')) hits.push('localhost')
      if (/\.example\.(com|org|net)\b/i.test(u)) hits.push('IANA 保留域名 *.example.*')
      if (u.includes('.invalid')) hits.push('.invalid')
      if (hits.length > 0) {
        // eslint-disable-next-line no-console
        console.warn(
          `[领翼golf] API_BASE_URL 不适合真机/体验版（${hits.join('、')}）。请在 client/.env.test.local 或 .env.production 填写真实 https API 后重建；HTTPS 须可信 CA（Let's Encrypt 见 infra/deploy/README.md）。`,
        )
      }
    }

    // W8-T1：隐私授权 — 登录走登录页 Button（agreePrivacyAuthorization），
    //   其它隐私 API 调用前走 `ensurePrivacyAuthorized`；不在 App 注册 onNeedPrivacyAuthorization。

    // W8-T2：最低基础库兜底。
    //   老版本微信跑 W8 的隐私 / 合规 API 会静默失败；这里 modal 提示用户升级。
    //   非 weapp 环境直接跳过。
    checkMinSdkVersion()

    // W8-T1：首启合规拦截。
    //   未同意当前版本协议 → reLaunch 到 consent 页。
    //   注意 reLaunch 会清空页面栈（分享/消息唤起带的 query 会丢失），
    //   这是合规必付的代价，不在合规流程里做 query 透传。
    if (!storage.hasAgreedCurrentTerms()) {
      deferReLaunch('/pages/consent/index')
    }

    // W8-T5：全局未捕获错误 → error_report 埋点。
    //   Taro 在小程序环境下把这两个 API 代理到 wx.onError / wx.onUnhandledRejection；
    //   H5 / RN 环境会静默 no-op（Taro 在非 weapp 下的兜底行为）。
    try {
      Taro.onError?.((err) => {
        trackError(err instanceof Error ? err : new Error(String(err)), {
          scope: 'app.onError',
        })
      })
      Taro.onUnhandledRejection?.((res) => {
        trackError((res as { reason?: unknown })?.reason, {
          scope: 'app.onUnhandledRejection',
        })
      })
    } catch {
      // 非 weapp 环境部分 API 未挂载；埋点不该影响主流程
    }
  }

  componentDidShow(options?: { scene?: number; path?: string }) {
    // W8-T5：App 级 page_view — scene（小程序启动场景值）+ path（首启落位页）
    //   同一次会话多次 onShow 都记一次（前后台切换也算一次活跃），
    //   对"日活 / 启动路径漏斗"更有参考价值。
    track('page_view', {
      level: 'app',
      scene: options?.scene,
      path: options?.path,
    })
  }

  componentDidHide() {
    // App 退后台时把剩余埋点冲一下，尽量不丢数据
    void flushTrack()
  }

  componentDidCatchError() {}

  render() {
    // W8-T2：EnvBadge 仅对 H5/RN 生效（App render 在小程序里会被忽略）；
    //   小程序侧角标通过各 tabBar 页（pages/index | coach | training | profile）
    //   手动挂一次 <EnvBadge />，覆盖主要入口即可。
    return (
      <>
        {this.props.children}
        <EnvBadge />
      </>
    )
  }
}

export default App
