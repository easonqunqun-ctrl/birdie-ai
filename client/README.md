# 客户端（Taro 3 · 微信小程序）

编译目标：**微信小程序**（`weapp`）。

> 原 React Native 端已下线，App 端改用独立 Flutter 工程（见 [`../docs/22-App-Flutter独立重写落地计划.md`](../docs/22-App-Flutter独立重写落地计划.md)）。`client/` 现只出微信小程序。

## 目录

```
client/
├── src/
│   ├── app.tsx / app.config.ts / app.scss   全局
│   ├── pages/                                页面（每个页面一个目录）
│   ├── services/                             API 调用层（与后端契约）
│   ├── store/                                Zustand 状态管理
│   ├── adapters/                             平台差异 API 封装（登录/拍摄等）
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
pnpm build:weapp:prod:check   # 正式包（先校验 .env.production）

pnpm type-check               # tsc --noEmit
pnpm lint                     # eslint
pnpm test                     # Jest 单测
```

## 视觉规范（与产品文档一致）

客户端配色与品牌气质以 [`src/app.scss`](./src/app.scss) 的 CSS 变量为 **唯一权威源**（白皮书 §7.2、AGENTS §3 均为其镜像描述）：**靛蓝 + 白 + 金 + 点缀绿**——靛蓝 `var(--color-primary)` 主色、白为阅读/卡片基色、金 `var(--color-gold)` 为小面积强调、点缀绿 `var(--color-accent-mint)` 仅用于「成长/完成/上行」语义。业务页面 / 组件应一律引用 `var(--color-*)` 变量，避免散落硬编码。

## 代码注意

- **平台差异 API** 一律走 `src/adapters/*`，不要在页面里直接 if-else
- **样式**：尽量用 flex 布局，避免复杂 selector
- **页面跳转**：始终用 `Taro.navigateTo` / `Taro.reLaunch`
