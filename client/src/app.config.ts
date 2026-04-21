/**
 * 全局应用配置
 *
 * W1 阶段 tabBar 暂未配置图标（设计师未出图），
 * 当前 tabBar 暂时关闭，等 W2 出图后再启用。
 */
export default defineAppConfig({
  pages: [
    'pages/index/index',
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
    'pages/profile/invitations'
  ],
  window: {
    backgroundTextStyle: 'light',
    navigationBarBackgroundColor: '#ffffff',
    navigationBarTitleText: '小鸟 AI',
    navigationBarTextStyle: 'black',
    backgroundColor: '#f7f8fa'
  },
  // tabBar: {
  //   color: '#999999',
  //   selectedColor: '#0f3d2e',
  //   backgroundColor: '#ffffff',
  //   borderStyle: 'black',
  //   list: [
  //     { pagePath: 'pages/index/index', text: '首页',
  //       iconPath: 'assets/tab/home.png', selectedIconPath: 'assets/tab/home_active.png' },
  //     { pagePath: 'pages/coach/index', text: 'AI 教练',
  //       iconPath: 'assets/tab/coach.png', selectedIconPath: 'assets/tab/coach_active.png' },
  //     { pagePath: 'pages/training/index', text: '训练',
  //       iconPath: 'assets/tab/training.png', selectedIconPath: 'assets/tab/training_active.png' },
  //     { pagePath: 'pages/profile/index', text: '我的',
  //       iconPath: 'assets/tab/profile.png', selectedIconPath: 'assets/tab/profile_active.png' }
  //   ]
  // },
  permission: {
    'scope.userLocation': {
      desc: '你的位置信息将用于推荐附近球馆'
    }
  },
  // Taro 3.6 的类型定义还没跟上微信最新的 `requiredPrivateInfos` 值范围；
  // `chooseMedia` 是微信官方允许的值（我们 W3 拍摄分析要用到），
  // 这里保留声明，按需忽略类型报错。
  // @ts-expect-error Taro 类型定义过窄，实际值被微信官方支持
  requiredPrivateInfos: ['chooseMedia']
})
