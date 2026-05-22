# 小程序正式上线：傻瓜步骤（ICP 已通过之后）

> 本文按「先做什么、后做什么」顺序写；**你在微信/云平台里点的步骤我替你做不了**，仓库里能自动化的已做成脚本 + `make` 命令。  
> 深度任务拆分仍以 [**`docs/17-W9任务拆分.md`**](../17-W9任务拆分.md) 为准。

---

## 第 0 步：弄清两件事

1. **ICP 域名备案**：你的 **API / 上传 / 下载用的域名**可以用 **HTTPS**，这是下面一切的前提之一。  
2. **微信小程序备案**：在 **微信公众平台** 里单独的一套；**正式发布前必须做完**（和 ICP 不是同一个按钮）。

---

## 第 1 步：微信公众平台（你来点，我无法代操作）

登录 [微信公众平台](https://mp.weixin.qq.com) → **开发 → 开发管理 → 服务器域名**，按实际上线的域名勾选（服务端均为 **HTTPS**，控制台里证书须有效）。

**填写格式（重要）**：微信开放平台 **`modify_domain` 接口示例**里，`requestdomain` 等为 **`https://` 开头的字符串**，例如 **`https://api.xxx.com`**（见 [官方文档](https://developers.weixin.qq.com/doc/oplatform/openApi/OpenApiDoc/miniprogram-management/domain-management/modifyServerDomain.html)）。公众平台网页后台若校验「必须使用 HTTPS」或拒绝纯主机名，请按 **`https://主机名`** 填写。**不要**带接口路径（如 **`/v1`**），也不要末尾多余的 `/`。  
（另一类「DNS 预解析域名」官方写明 **无需协议头**，勿与本页的「服务器域名」混淆。）

| 类型 | 要填什么（按你实际架构） |
|------|---------------------------|
| **request 合法域名** | 后端 API 主机，与 **`TARO_APP_API_BASE_URL`** **同源**：例如 **`https://api.xxx.com`** |
| **uploadFile 合法域名** | **`wx.uploadFile` 直连上传**的目标；本项目 MinIO 经 nginx 反代时，预签名 URL 的 host 应与 **`MINIO_PUBLIC_ENDPOINT`** 一致（常为 API 同主机 **`https://api.xxx.com`**，否则填签名 URL 里的真实 **`https://…`**） |
| **downloadFile 合法域名** | **`Taro.downloadFile` / 视频播放 / 海报小程序码** 等资源下载 host；MinIO 反代在同主机时与 API **同源**（见下表）；切 COS/CDN 后改为 CDN 主机，例如 **`https://video.xxx.com`** |

**当前 CVM staging / 体验版已登记（2026-05-21，产品确认）**

| 类型 | 已填域名 | 用途说明 |
|------|----------|----------|
| **request** | `https://api.birdieai.cn` | API `/v1/*` |
| **uploadFile** | `https://api.birdieai.cn` | MinIO 预签名直传（`/minio/…`） |
| **downloadFile** | `https://api.birdieai.cn` | 报告视频/缩略图、**分享海报小程序码**（`share/wxa/*.png` 等，经 `/minio` 反代） |

**说明**：本项目教练页 SSE 走的是 **HTTPS 请求 + 分块**（[`client/src/utils/sseClient.ts`](../../client/src/utils/sseClient.ts)），**不是 WebSocket**，一般**不用**再单独配「socket 合法域名」，只要 **request** 里已有 API 域名即可。

另：**开发 → 基本配置** 里完成 / 核对 **小程序备案**、**用户隐私保护指引**、**服务类目**（见 W9 T6）。

---

## 第 2 步：HTTPS 与后端（你来部署，我替不了）

1. 生产环境 **API** 已部署，浏览器或 `curl` 能访问：  
   `https://你的API域名/v1/health` → 返回 JSON `ok` 之类。  
2. 若已切 **腾讯云 COS**：后端 `STORAGE_PROVIDER=cos` 且桶/CORS/CDN 已配；否则仍用 MinIO 仅适合内测。  
3. **小程序上传体验版 / 提交审核**：务必使用 **`make client-build-weapp-prod`**（或 `pnpm build:weapp:prod:check`），勿长期使用占位 **`TARO_APP_API_BASE_URL`** 的 test 包误传体验版。  
4. 真登录：**生产 / CVM 体验环境必须 `WECHAT_MOCK_LOGIN=false`**，并配置真实 **AppID / Secret**（根目录 `.env.example` 已标注）；若为 `true`，会出现 mock openid / 行为异常，排查困难。
5. 真支付（若已开）：**商户号 + APIv3 + 回调 URL** 与后台「支付」配置一致。

---

## 第 3 步：填客户端生产环境变量（你来改一行，我写好模板）

打开 **[`client/.env.production`](../../client/.env.production)**，把 **`TARO_APP_API_BASE_URL`** 改成你的 **正式 API**（须 **https**，且带 **`/v1`** 后缀，与客户端 [`config/index.ts`](../../client/config/index.ts) 约定一致）：

```bash
TARO_APP_API_BASE_URL=https://api.你的备案域名/v1
TARO_APP_ENV=production
```

其它项（`TARO_APP_PAYMENT_*`、`TARO_APP_SUBSCRIBE_TMPL_IDS`）按 W9 与业务开关调整；**不要**把含密钥的文件提交到 Git。

---

## 第 4 步：库里一键打「正式包」（我能帮你固定成命令）

在**仓库根目录**执行：

```bash
make client-build-weapp-prod
```

它会：

1. 运行 **`client/scripts/check-weapp-prod-env.sh`**：检查 **`client/.env.production`** 里 API 是否为 **https**、非空、非 `localhost`；不通过会直接退出。  
2. 执行 **`pnpm build:weapp:prod`** → 产出在 **`client/dist/`**。

若 CI 里无法读你的 `.env.production`，可设 **`SKIP_WEAPP_PROD_ENV_CHECK=1`** 跳过检查（不推荐日常手操使用）。

等价命令：

```bash
cd client && pnpm build:weapp:prod:check
```

---

## 第 5 步：微信开发者工具（你来上传）

1. 打开 **微信开发者工具** → 导入项目 → 目录选 **`client`**（与 `project.config.json` 同级），**`miniprogramRoot`** 指向 **`dist/`**。  
2. **详情 → 本地设置**：  
   - 开发时可勾选「**不校验合法域名**」；  
   - **提交审核 / 正式上线前**，应依赖 **第 1 步**配置的合法域名，并在真机上**关掉**该项做一次验证。  
3. **上传** → 微信公众平台 **版本管理** 里设为**体验版**或**提交审核**。

---

## 第 6 步：最短验收清单（打勾即用）

- [ ] `https://api…/v1/health` 通  
- [ ] 微信公众平台 **request**（及 upload/download 若用到）已与上面域名一致  
- [ ] 真机：**登录 → 上传/分析 → 报告 → 教练对话**（关「不校验域名」仍能跑）  
- [ ] 正式包：**右上角无环境角标**（[`EnvBadge`](../../client/src/components/EnvBadge.tsx) 在生产为 `production`）  
- [ ] 支付若要上：**沙箱 / 小额真付**走完一单  

---

## 附录：线上**测试**发版（W8，非正式 ICP 路径）

与上文「正式上线」不同：测试栈是 **CVM 单机 + Docker + nginx + HTTPS**。  
- **开发者工具调试**：可用 **自签**证书并勾选「不校验合法域名 / TLS / 证书」（见 Runbook）。  
- **微信小程序体验版 / 真机**：自签会触发 **`request:fail errcode:-207`**，须在 CVM 换 **Let's Encrypt 等可信 CA**（仓库命令：`make issue-le-cert` / `make renew-le-cert`，说明 **[`infra/deploy/README.md`](../../infra/deploy/README.md)**）。

1. **CVM**：装 Docker → `git clone` 到 `/opt/xiaoniao`（或等价目录）。
2. **后端环境**：`cp .env.test .env.local`，替换所有 `<...>`；务必把 **`BACKEND_CORS_ORIGINS`** 设为 **`https://<测试主机或 IP>`**，**`MINIO_PUBLIC_ENDPOINT`** 设为 **`https://<同一主机>/minio`**（与公众平台 **uploadFile** host 对齐）。
3. **证书与起栈**：`make test-certs HOST=<同上主机或域名>` → `make deploy-test` → **`make issue-le-cert EMAIL=<邮箱> DOMAIN=<同上域名>`**（真机必需）→ `make test-health HOST=<同上>`。
4. **云安全组**：放行 **22 / 80 / 443**；不要放行 8000、5432、6379、9000 等（由 nginx 反代）。
5. **小程序包（在你本机打）**：体验版建议 **`make client-build-weapp-prod`**；若仍用 **`pnpm build:weapp:test`**，必须用 **`.env.test.local`** 覆盖 **`TARO_APP_API_BASE_URL=https://<测试主机>/v1`**（与 CVM **HTTPS**、可信 CA 一致）。
6. **微信开发者工具**：导入 **`client`**，**miniprogramRoot = `dist/`**；真机验收前应关闭「不校验合法域名」或至少在真机上验证一次。

**逐步截图与踩坑表**：[**`docs/release-notes/W8-test-env-runbook.md`**](./W8-test-env-runbook.md)。

---

## 发版记录（体验版 / 提审）

| 版本 | 状态 | 备注 |
|------|------|------|
| **1.0.3** | 已提审 | MVP 主链路 + Batch-A～F |
| **1.0.4** | 已交付 | 到期弹窗扩散、版本号对齐 |
| **1.1.0** | 已交付 | 打卡月历、朋友圈分享、analysis_card、邀请分档 |
| **1.1.1** | 开发中 | video_card + P-02；见 [`v1.0.4-plus-roadmap.md`](./v1.0.4-plus-roadmap.md) |

---

## 相关文档

- [**`v1.0.4-plus-roadmap.md`**](./v1.0.4-plus-roadmap.md)（post-1.0.3 版本计划）
- [**`infra/deploy/README.md`**](../../infra/deploy/README.md)（Let's Encrypt：`issue-le-cert` / `renew-le-cert`）  
- [**`docs/17-W9任务拆分.md`**](../17-W9任务拆分.md)  
- [**`docs/release-notes/W9-tencent-cloud-purchase-list.md`**](./W9-tencent-cloud-purchase-list.md)  
- [**`docs/release-notes/W8-test-env-runbook.md`**](./W8-test-env-runbook.md)（线上测试环境）
