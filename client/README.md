# 客户端（Taro 3 双端）

一份代码，编译两端：
- **微信小程序** (`weapp`)
- **React Native App** (`rn` → iOS / Android)

## 目录

```
client/
├── src/
│   ├── app.tsx / app.config.ts / app.scss   全局
│   ├── pages/                                页面（每个页面一个目录）
│   ├── services/                             API 调用层（与后端契约）
│   ├── store/                                Zustand 状态管理
│   ├── adapters/                             跨端适配（登录/拍摄等差异 API）
│   ├── utils/                                工具函数
│   └── types/                                TypeScript 类型
├── config/                                   Taro 编译配置
├── project.config.json                       微信开发者工具配置
├── tsconfig.json
└── package.json
```

## 命令

```bash
pnpm install                  # 装依赖

# 微信小程序
pnpm dev:weapp                # 监听模式，输出到 dist/（见 config outputRoot）
pnpm build:weapp              # 生产构建

# React Native App
pnpm build:rn                 # 生成 RN 工程到 dist/rn
pnpm dev:rn                   # 监听
# 还需要 cd 到 RN 工程后用 react-native 命令实际跑模拟器（W2 接入完整 RN 工程）
```

## 视觉规范（与产品文档一致）

客户端配色与品牌气质以仓库根目录 [`小鸟AI高尔夫-产品设计白皮书.md`](../小鸟AI高尔夫-产品设计白皮书.md) **§7.2 产品视觉规范** 为准：**深绿 + 白 + 金**（深绿主色、白为阅读/卡片基色、金为小面积点缀）。全局 Token 建议集中在 `src/app.scss` 维护，并与白皮书中的建议工程色值对齐后再迭代。

## 跨端代码注意

- **平台差异 API** 一律走 `src/adapters/*`，不要在页面里直接 if-else
- **样式**：尽量用 flex 布局，避免使用 RN 不支持的 CSS（grid、float、复杂 selector）
- **页面跳转**：始终用 `Taro.navigateTo` / `Taro.reLaunch`
- **判断当前端**：`process.env.TARO_ENV === 'weapp' | 'rn'`
