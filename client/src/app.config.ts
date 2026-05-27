/**
 * 全局应用配置
 */
export default defineAppConfig({
  /** 微信代码质量「组件按需注入」；基础库 ≥ 2.11.1 */
  lazyCodeLoading: 'requiredComponents',
  pages: [
    'pages/index/index',
    'pages/consent/index',
    'pages/legal/terms',
    'pages/legal/privacy',
    'pages/help/score-guide',
    'pages/login/index',
    'pages/onboarding/index',
    'pages/analysis/capture',
    'pages/analysis/params',
    'pages/analysis/waiting',
    'pages/analysis/report',
    'pages/analysis/poster',
    'pages/analysis/history',
    'pages/analysis/compare',
    'pages/coach/index',
    'pages/training/index',
    'pages/profile/index',
    'pages/profile/edit',
    'pages/profile/membership',
    'pages/profile/invitations',
    'pages/profile/chat-history',
    'pages/profile/account-deletion',
    'pages/profile/feedback',
    'pages/profile/settings',
    'pages/profile/about',
    'pages/profile/clubs',
    'pages/courses/index',
    'pages/courses/detail',
    'pages/pros/index',
    'pages/pros/detail'
  ],
  /**
   * 说明：真机上 wx.request **单次等待完整响应**仍有约 60s 量级上限；
   * AI 教练已默认走 chunked SSE，此项主要服务于其它长请求或开发者工具。
   */
  networkTimeout: {
    request: 420000,
    connectSocket: 60000,
    downloadFile: 180000,
    /** 视频直传 MinIO（analysisService.uploadToMinio）；弱网适当放宽 */
    uploadFile: 300000,
  },
  window: {
    backgroundTextStyle: 'light',
    navigationBarBackgroundColor: '#ffffff',
    navigationBarTitleText: '领翼golf',
    navigationBarTextStyle: 'black',
    backgroundColor: '#f4f6fc'
  },
  tabBar: {
    color: '#888888',
    selectedColor: '#1a237e',
    backgroundColor: '#ffffff',
    borderStyle: 'black',
    list: [
      {
        pagePath: 'pages/index/index',
        text: '首页',
        iconPath: 'assets/tab/home.png',
        selectedIconPath: 'assets/tab/home_active.png'
      },
      {
        pagePath: 'pages/coach/index',
        text: 'AI 教练',
        iconPath: 'assets/tab/coach.png',
        selectedIconPath: 'assets/tab/coach_active.png'
      },
      {
        pagePath: 'pages/training/index',
        text: '训练',
        iconPath: 'assets/tab/training.png',
        selectedIconPath: 'assets/tab/training_active.png'
      },
      {
        pagePath: 'pages/profile/index',
        text: '我的',
        iconPath: 'assets/tab/profile.png',
        selectedIconPath: 'assets/tab/profile_active.png'
      }
    ]
  },
  /**
   * 隐私接口合规说明（避免后人再踩同一坑）：
   *
   * 1) `requiredPrivateInfos`：**只**接受位置类 8 个 API（chooseAddress / chooseLocation /
   *    choosePoi / getFuzzyLocation / getLocation / onLocationChange /
   *    startLocationUpdate / startLocationUpdateBackground）；写其它值会被开发者工具
   *    静态校验拒绝。一期不取定位，整段不声明。
   *
   * 2) `permission`：**只**接受官方白名单（scope.userLocation / scope.userLocationBackground /
   *    scope.userFuzzyLocation / scope.writePhotosAlbum / scope.werun / scope.bluetooth /
   *    scope.invoice / scope.invoiceTitle / scope.workSubArea 等）；
   *    `scope.camera` / `scope.record` 等运行时存在的 scope **不在** app.json 白名单里，
   *    误写会触发开发者工具「无效的 app.json permission[xxx]」红字。
   *    摄像头授权由 `chooseMedia` / `createCameraContext` 在运行时弹窗，不需要在此声明。
   *
   * 3) 媒体类合规真正落地的两处：
   *    a) 代码运行时：`adapters/media.ts` 调 `ensurePrivacyAuthorized` → `wx.requirePrivacyAuthorize`
   *    b) 公众平台：设置 → 服务内容声明 → 用户隐私保护指引，勾「摄像头」「上传图片视频」并提交审核
   *
   * 参考：
   *  - https://developers.weixin.qq.com/miniprogram/dev/reference/configuration/app.html#requiredPrivateInfos
   *  - https://developers.weixin.qq.com/miniprogram/dev/reference/configuration/app.html#permission
   */
  permission: {
    /** Q-C1 分享海报：保存到相册时弹的授权说明文案 */
    'scope.writePhotosAlbum': {
      desc: '将挥杆报告海报保存到您的相册，便于分享到朋友圈',
    },
  },
})
