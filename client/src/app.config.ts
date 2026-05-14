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
    'pages/login/index',
    'pages/onboarding/index',
    'pages/analysis/capture',
    'pages/analysis/params',
    'pages/analysis/waiting',
    'pages/analysis/report',
    'pages/analysis/history',
    'pages/coach/index',
    'pages/training/index',
    'pages/profile/index',
    'pages/profile/edit',
    'pages/profile/membership',
    'pages/profile/invitations',
    'pages/profile/chat-history',
    'pages/profile/account-deletion'
  ],
  /** 对话 SSE 首轮 token 较慢；略高于 wx.request/sseClient timeout，对齐 chatService */
  networkTimeout: {
    request: 180000,
    connectSocket: 60000,
    downloadFile: 180000,
    uploadFile: 180000,
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
  }
})
