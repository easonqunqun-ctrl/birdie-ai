/** weapp 打包占位：禁止打入 RN 本体（Flow/import typeof 等 webpack 无法解析） */
module.exports = {
  Platform: {
    OS: 'web',
    Version: 1,
    select: function (spec) {
      return spec.web
    },
  },
}
