export default definePageConfig({
  navigationBarTitleText: '分享海报',
  navigationBarBackgroundColor: '#1a237e',
  navigationBarTextStyle: 'white',
  backgroundColor: '#f4f6fc',
  /**
   * 海报页本身不参与下拉刷新；
   * Canvas 渲染靠按钮触发，避免误触造成卡顿。
   */
  enablePullDownRefresh: false,
})
