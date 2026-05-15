# React Native 壳工程（与本仓库联调）

业务 JS 在 [`client/`](./) 源码树；原生 **`ios/` / `android/`** 由 **`taro-native-shell`** 提供。**不要**在未 clone 时在空目录手写 Podfile——一律走 bootstrap。

## 一键 bootstrap（幂等）

在仓库根或 `client/`：

```bash
make client-bootstrap-rn-shell
# 或 cd client && pnpm setup:rn-shell
```

克隆后的 **`client/rn-shell/*`**（含 `ios/`、`android/`、`.git`）默认已由 **[`client/.gitignore`](.gitignore)** 排除，避免误提交 upstream 宿主；仓库里只跟踪 **`rn-shell/README.md`** 占位。若你已把整壳拷进索引，需 **`git rm -r --cached client/rn-shell`** 后再按上述 ignore 重来。

- 源码：`https://github.com/NervJS/taro-native-shell.git`
- **分支：** `0.70.0`（与 RN **0.70.x**、本仓 **react-native 0.70.15**、Taro **3.6.x** 对齐；见 [官方兼容表](https://docs.taro.zone/docs/react-native)）
- 覆盖环境变量：`RN_SHELL_REPO_URL`、`RN_SHELL_BRANCH`

若 `rn-shell/` 除 `README.md` 外还有其他文件会**中止**，避免误删。

## Pods（iOS）

```bash
cd client/rn-shell/ios
bundle install
bundle exec pod install
```

用 **`.xcworkspace`** 打开工程。卡住时参见壳仓库 Issue（Ruby/CocoaPods 版本、`USE_FRAMEWORKS` / Flipper）。

## Android

```bash
cd client/rn-shell/android && ./gradlew :app:assembleDebug
```

## 与业务 RN 配置的衔接

[`client/config/rn.ts`](config/rn.ts) 配置了**分离模式**产物路径（`main.jsbundle`、`index.android.bundle`）及 **`appName: 'taroDemo'`**（与官方壳原生模块名一致）。若改名为 `xiaoniaoai`，需按 Taro 文档同步改壳工程 **AppDelegate / MainActivity** 并重清 Metro。

## 原生依赖（微信、相册）

bootstrap 之后在业务仓执行：

```bash
cd client && pnpm rn-shell:deps-hint
```

按输出在 **`client/rn-shell`** 目录执行 **`yarn add` / `pnpm add`**。**开放平台 URL Scheme / Universal Links / Android 签名**仍为团队密钥配置。

## 常用命令小结

```bash
cd client
pnpm install
pnpm dev:rn              # Metro
pnpm build:rn -- --platform ios   # 产物写入 rn-shell/ios（见 config/rn.ts）
cd rn-shell && yarn ios           # 或 npm 脚本等价物
```

## 自动化门禁（无模拟器）

在仓库根：

```bash
make client-check-rn     # bundle 门禁 + client type-check；已并入 make test
```

详见 [`docs/release-notes/W10-rn-smoke-checklist.md`](../docs/release-notes/W10-rn-smoke-checklist.md) 第 8 节。
