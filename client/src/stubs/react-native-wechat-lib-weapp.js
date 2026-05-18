/* eslint-disable import/no-commonjs -- weapp 占位须 CommonJS 以适配 webpack alias */
/** weapp 打包占位：RN 微信 SDK 仅在 taro build --type rn 使用 */
module.exports = {
  default: {
    registerApp: async function () {
      return false
    },
    sendAuthRequest: async function () {
      return { errCode: -1, errStr: 'react-native-wechat-lib stub (weapp)' }
    },
  },
}
