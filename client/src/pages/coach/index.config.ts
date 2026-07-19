export default definePageConfig({
  navigationBarTitleText: 'AI 教练',
  // 不允许用户下拉刷新：历史消息由 `useDidShow` bootstrap 时拉取
  enablePullDownRefresh: false,
  // 白底导航看起来比灰底页面更聚焦
  navigationBarBackgroundColor: '#ffffff',
  navigationBarTextStyle: 'black',
  enableShareAppMessage: true,
  enableShareTimeline: true,
})
