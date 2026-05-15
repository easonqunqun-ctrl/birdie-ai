/**
 * 微信小程序 webpack 打包占位模块。
 * 真机构图使用 src/adapters/media.ts 内 Taro.chooseMedia；RN 端不使用此文件。
 */
function rejectStub() {
  return Promise.reject(new Error('react-native-image-picker 仅在 React Native 构建中可用'))
}

module.exports = {
  launchCamera: rejectStub,
  launchImageLibrary: rejectStub,
}
