# W8 真机开测 · Preflight Checklist（10 分钟体检）

> **用途**：团队真机内测**开始前**统一跑一遍；任意一条红就暂停，先修好再上人测。
>
> **前置**：CVM 已按 [W8-test-env-runbook](./W8-test-env-runbook.md) 跑过 `make deploy-test`，拿到 `$HOST`（IP 或解析到 CVM 的域名）。

---

## 0. 速查命令（全部可复制）

```bash
HOST=<CVM IP 或 域名>            # 下文所有命令用到
SSH="ssh ubuntu@$HOST"            # 如果你是 ubuntu；root 换一下
```

---

## 1. 环境变量（CVM 侧 `.env.local`）

```bash
$SSH 'cd ~/xiaoniao && grep -E "^(APP_ENV|WECHAT_MOCK_LOGIN|QUOTA_MODE|WECHAT_PAY_MOCK_MODE|WECHAT_MINIPROGRAM_APPID|WECHAT_MINIPROGRAM_SECRET|DEEPSEEK_API_KEY)=" .env.local | sed -E "s/(SECRET|KEY|APPID)=.*/\1=***redacted***/"'
```

**应当看到**（值自行对照）：

| 变量 | 测试环境期望 | 说明 |
|---|---|---|
| `APP_ENV` | `test` | 影响日志 / error trace 行为 |
| `WECHAT_MOCK_LOGIN` | **`false`** | 真机登录必须关 mock（T4） |
| `QUOTA_MODE` | **`unlimited`** | 内测不卡配额（T3） |
| `WECHAT_PAY_MOCK_MODE` | `true` | 支付保持 mock（W9 前不开真支付） |
| `WECHAT_MINIPROGRAM_APPID` | 真实值 | 小程序后台拷 |
| `WECHAT_MINIPROGRAM_SECRET` | 真实值 | 同上；泄露后立刻在后台重置 |
| `DEEPSEEK_API_KEY` | 真实值 | 对话 SSE 依赖 |

**红灯**：`WECHAT_MOCK_LOGIN=true` → 真机登录会因为 openid 不一致连不上；立即改成 false 并 `make test-restart`。

---

## 2. Docker 栈健康（5 项必须 healthy / running）

```bash
$SSH 'cd ~/xiaoniao && make test-ps'
```

**应当看到**（Status 列）：

| 服务 | 期望状态 |
|---|---|
| `postgres` | `Up ... (healthy)` |
| `redis` | `Up ... (healthy)` |
| `minio` | `Up` |
| `backend` | `Up` |
| `celery-worker` | `Up` |
| `ai_engine` | `Up` |
| `nginx` | `Up` |

**红灯**：任一 `Exit` / `Restarting` → `make test-logs` 看尾部；常见是 `.env.local` 缺字段或端口被占用。

---

## 3. HTTPS + 证书

```bash
# nginx 443 起来没
$SSH 'ss -ltn | grep -E ":(80|443) "'

# 证书到期时间（自签 365 天）
$SSH 'openssl x509 -in ~/xiaoniao/infra/test/certs/server.crt -noout -dates -subject'
```

**应当看到**：
- `0.0.0.0:80` + `0.0.0.0:443` 都在 LISTEN
- `notAfter` 至少 > 1 个月；`subject` 里 `CN=$HOST` 与你填的一致

**红灯**：证书已过期 → `make test-certs HOST=$HOST && make test-restart`。

---

## 4. 健康接口

```bash
# 后端 /v1/health（经过 nginx → backend）
curl -fk -m 5 https://$HOST/v1/health

# AI Engine 通过后端的内网调用（间接，看 backend 日志里有没有 "ai_engine_up"）
$SSH 'cd ~/xiaoniao && docker compose -f docker-compose.yml -f docker-compose.test.yml logs --tail=50 backend | grep -E "ai_engine|startup"'
```

**应当看到**：
- `/v1/health` 返回 200 + JSON（`{"code":0,"data":{"status":"ok",...}}`）
- backend 启动日志里 `db_connected` / `redis_connected` / `ai_engine_up` 等关键 OK

**红灯**：`/v1/health` curl 超时 / 502 → nginx → backend 链路断；看 `make test-logs` 找 upstream 报错。

---

## 5. 微信侧配置（小程序后台）

打开 [mp.weixin.qq.com](https://mp.weixin.qq.com) 对号入座：

- [ ] **开发设置 → AppID / AppSecret**：与 CVM `.env.local` 里一致
- [ ] **开发设置 → 服务器域名**：测试期**不用配**（开发者工具勾"不校验合法域名"即可；备案前也配不了 IP）
- [ ] **版本管理 → 体验版**：开发者扫"预览二维码"会走开发版，不需要体验版权限；但如果想让团队里**非开发者**的同事内测，**必须在体验版白名单加他的 openid**
- [ ] **用户隐私保护指引**：W8-T1 已提交过一次；如有字段变动重新提交等 1-2 日审核
- [ ] **基础库**：开发者工具里选 ≥ `2.27.1`（W8-T2 设定的最低线）

---

## 6. 客户端侧

```bash
# 本机开发机上
cd client
cat .env.test | grep -E "^TARO_APP_" | sed -E "s/(SECRET|KEY)=.*/\1=***/"
```

**应当看到**：
- `TARO_APP_API_BASE_URL=https://$HOST/v1`（必须 https + 指向 CVM）
- `TARO_APP_PAYMENT_ENABLED=false`
- `TARO_APP_PAYMENT_MOCK=true`

**编译 + 上传预览**：

```bash
cd client
pnpm build:weapp                       # 或 pnpm dev:weapp 热更新也行
# 开发者工具 → 导入 client/dist → 上方"预览"生成二维码 → 真机扫码
```

**开发者工具必勾项**：
- [ ] `详情 → 本地设置 → 不校验合法域名 / 不校验 HTTPS / TLS 版本` ✅
- [ ] `基础库`：≥ 2.27.1
- [ ] 右上角"预览"→ "自动预览"关掉，手动扫码更稳

---

## 7. 测试账号（3 张卡）

| 账号 | 用途 | 准备工作 |
|---|---|---|
| **A · 本人微信** | 走正常 onboarding → 拍摄 → 分析 → 对话 → 分享闭环 | 无 |
| **B · 同事微信** | 被 A 邀请注册 / 被 A 分享接收方 | 加 openid 到体验版白名单（非开发者才需要） |
| **C · 会员账号（A 开 mock 会员）** | 验证会员分支（无限配额 / 专属文案 / 会员角标） | `bash scripts/mock_pay.sh <A.openid> monthly`（详见 [walkthrough](./W8-internal-walkthrough.md) §附录 A） |

**拿 openid 最快的办法**：A 在真机第一次登录后，`$SSH 'cd ~/xiaoniao && docker compose exec -T postgres psql -U xiaoniao -d xiaoniao -c "SELECT id, wechat_openid, nickname, created_at FROM users ORDER BY created_at DESC LIMIT 5;"'` 看最新一行。

---

## 8. 测试素材（放 `docs/release-notes/W8-evidence/source-media/`）

| 素材 | 用途 | 建议来源 |
|---|---|---|
| `swing_normal.mp4` | 正常挥杆，3-10s，≤ 50MB | 自己手机拍一段 |
| `swing_too_short.mp4` | 1s 左右，用于验"时长过短" | 截原视频前 1s |
| `violation_sample.jpg`（或文件名含 `violation`） | 验证 `mediaCheck` 违规分支（mock 模式下文件名匹配即拒） | 随便一张图改名 `violation_xxx.jpg` |
| `invite_other_device_qr.png` | 被邀请者扫码用的图（可选） | 小程序码生成 |

---

## 9. 走查前最后 2 件事

- [ ] `docs/release-notes/W8-evidence/` 子目录建好（见 [walkthrough §证据归档](./W8-internal-walkthrough.md)）
- [ ] 开一个白板或共享文档（腾讯文档 / Notion）记录 **P0 bug 实况**，边测边写；测完直接拷贝到 walkthrough 第六节

---

## 10. 一键体检（懒人版）

在开发机上跑：

```bash
HOST=<CVM IP 或 域名>

echo "=== /v1/health ===" && curl -skf -m 5 "https://$HOST/v1/health" && echo ""
echo "=== cert days left ===" && echo | openssl s_client -connect "$HOST:443" -servername "$HOST" 2>/dev/null | openssl x509 -noout -enddate
echo "=== root 404 expected ===" && curl -sk -o /dev/null -w "%{http_code}\n" -m 5 "https://$HOST/"
echo "=== upload presign reachable (401 ok) ===" && curl -sk -o /dev/null -w "%{http_code}\n" -m 5 -X POST "https://$HOST/v1/analyses/upload-token"
```

**绿灯判据**：
- `/v1/health` 返回 JSON（非空）
- 证书到期 > 30 天
- `/` → `404`（nginx catch-all）
- `/v1/analyses/upload-token` → `401`（需要 Token，说明网关 → 后端 → 鉴权链通）

任意红灯直接回到对应 §。10 分钟搞完就开工。
