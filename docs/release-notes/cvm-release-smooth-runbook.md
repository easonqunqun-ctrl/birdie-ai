# CVM 顺滑发版 Runbook（踩坑规避）

> 目标：**本机一条命令触发 Git 发版**，尽量少 SSH 进服务器；出问题能按表自查。  
> 主干约定见 [**`CVM-canonical-deploy.md`**](CVM-canonical-deploy.md)。

---

## 一、角色分工（避免在错的环境执行）

| 在哪里 | 做什么 |
|--------|--------|
| **Mac（仓库根）** | `git` 提交/推送、`make client-build-weapp-prod`、`make setup-cvm-ssh-key`（仅一次）、`make ship-cvm` / `make release-cvm` |
| **CVM（服务器）** | 维护 `.env.local`、**仅在排障**时 `docker logs` / `docker compose ps`；日常发版**不必**登录执行 `make`（Mac 已 SSH 触发脚本） |

**常见错误**：在服务器 `~` 下敲 `make release-cvm` → 找不到 Makefile；在服务器跑 `setup-cvm-ssh-key` → 应在 **Mac** 上跑。

---

## 二、一次性准备（每台 Mac / 每个部署员）

1. **SSH 免密**（只需成功一次；会提示最后一次服务器密码）：
   ```bash
   cd /path/to/lingniao-golf
   DEPLOY_HOST=ubuntu@<公网IP> make setup-cvm-ssh-key
   ```
2. **生产 secrets 文件**（用于**本机预检**，与开发 `.env.local` 分离）：例如 `~/secrets/lingniao-prod.env`，**勿含** trycloudflare/ngrok、尖括号占位符。
3. **Git 远端**：`git remote` 建议使用 **SSH**（`git@github.com:...`），避免 HTTPS `Connection reset`。
4. **小程序**：`client/.env.production` 里 `TARO_APP_API_BASE_URL` 为 `https://api.<域名>/v1`。

---

## 三、日常发版（推荐闭环）

在 **Mac 仓库根**、当前工作已合并到 **`main`**：

```bash
DEPLOY_HOST=ubuntu@<公网IP> ENV_FILE=~/secrets/lingniao-prod.env make ship-cvm
```

含义：**本机预检**（占位符 + 微信支付 compose）→ **`git push origin main`** → **SSH 远端**执行 `release-cvm-on-server.sh`（`pull` + `compose up --build` + `alembic` + nginx）。

若代码已 push，只触发远端：

```bash
DEPLOY_HOST=ubuntu@<公网IP> CVM_LOCAL_PREFLIGHT=1 ENV_FILE=~/secrets/lingniao-prod.env make release-cvm
```

发版后外网粗验：

```bash
curl -sfS https://api.birdieai.cn/v1/health
# 可选
make cvm-smoke DOMAIN=api.birdieai.cn
```

客户端：

```bash
make client-build-weapp-prod
```

用微信开发者工具打开 `client/dist` 上传体验版。

---

## 四、服务端 Git：脏工作区（提前拦截）

症状：`git pull` 报 *would be overwritten by merge* / *untracked files would be overwritten*。

**原因**：有人在 CVM 仓库里留下了**未提交修改**或**与远端重名未跟踪文件**，镜像可能打到「半套本地半套远端」。

**从本机推行的惯例**：

- 发版机 **`~/lingniao-golf` 只当构建机**：不在上面手改业务代码；要改在 Mac 上改完 **push** 再发版。
- 自 **`release-cvm-on-server.sh`** 起：默认若 `git status` 不干净会直接 **失败**，并打印修复命令；**不要**日常使用 `ALLOW_DIRTY_GIT=1`，仅应急。

**确认无未备份内容后**在 CVM 仓库根对齐远端（示例分支 `main`）：

```bash
cd ~/lingniao-golf
git fetch origin
git reset --hard origin/main
git clean -fd
```

然后再由 Mac 执行 `make release-cvm`（不要只在服务器上盲目 `compose up` 而跳过 `pull`）。

---

## 五、`ship-cvm` 与分支

- **`make ship-cvm` 仅允许在本地 `main` 上执行**，且只 **`git push origin main`**，与远端默认 **`GIT_BRANCH=main`** 一致，避免「push 了 feature 但服务器仍拉 main」的静默失败。
- 若必须发版**非 main**（少见）：在 Mac 上手动 `git push` 后执行：
  ```bash
  DEPLOY_HOST=ubuntu@<IP> GIT_BRANCH=<分支或tag> make release-cvm
  ```

---

## 六、`backend` 容器一度 `unhealthy`

**常见原因**：冷启动先跑 **`alembic`** 再起 **多 worker**，健康检查在窗口内未连上 `/v1/health`。

**处理**：等 2～3 分钟再 `docker compose ... ps`；看 `docker logs xiaoniao-backend --tail 80` 是否已有 `200` on `/v1/health`。持续失败再查日志里的 Traceback / DB 连接 / 迁移错误。

若**每次**发版都超时，再考虑加大 `docker-compose.test.yml` 里 backend 的 `start_period` / `retries`（属调参，非首选）。

---

## 七、自检清单（发版前 30 秒）

- [ ] Mac 上 **`git status`**：待发版改动已提交，且目标在 **`main`**
- [ ] **`git push`** 已成功（远端可见最新 commit）
- [ ] **`ENV_FILE` 预检**能过，或已跑 `make cvm-preflight ENV_FILE=...`
- [ ] CVM 上 **`.env.local` 存在**（密钥不提交 Git，只存在于服务器）
- [ ] 发版后 **`/v1/health`** 与小程序关键路径各点一条

---

## 七·补 发版前 5 分钟巡检（U-1～U-4 紧急队列）

> 与 [`docs/19-产品开发迭代计划-当前队列.md`](../19-产品开发迭代计划-当前队列.md) **§二 紧急队列**逐项对齐。脚本本身只做**只读**校验，不会写远端。

| 巡检项 | 命令 | 通过标志 |
|--------|------|---------|
| **U-1** Celery beat 在线 + 近 30min 派发 + 阈值 | `DEPLOY_HOST=ubuntu@<IP> make check-cvm-beat` | 三段全部 `✓`；阈值 `PAYMENT_PENDING_ORDER_EXPIRE_MINUTES > 0` |
| **U-2** COS / CDN 真桶 | `COS_BUCKET=… COS_REGION=… COS_SECRET_ID=… COS_SECRET_KEY=… [CDN_HOST=…] make check-cos-smoke` | PUT/HEAD/GET/CORS/DELETE 五步全过；CDN 段有节点头 |
| **U-3** HTTPS + 小程序合法域名 | `make check-weapp-domains` | 每个 host TLS 链合法、`/v1/health` 2xx；输出可粘贴的服务器域名清单 |
| **U-4** 支付/退款回调路径 | `ENV=$HOME/secrets/lingniao-prod.env make check-pay-callbacks` | NOTIFY_URL 路径精确等于 `/v1/payments/wechat/notify`；REFUND 同理 |

聚合入口：

```bash
ENV=$HOME/secrets/lingniao-prod.env make check-preflight
# 提示打印 U-1 / U-3 / U-2 的命令；按业务需要逐条执行
```

**注意**：U-2 涉及真凭据，**不要**把 `COS_SECRET_*` 写进 Makefile 或 .env 入库。命令行 inline 或临时 source 一个**未跟踪**的 `~/secrets/cos-smoke.env`。

---

## 八、附录：命令速查

| 场景 | 命令（在 Mac 仓库根，按需带 `DEPLOY_HOST=`） |
|------|-----------------------------------------------|
| 免密初始化 | `DEPLOY_HOST=ubuntu@IP make setup-cvm-ssh-key` |
| 预检 only | `make cvm-preflight ENV_FILE=~/secrets/lingniao-prod.env` |
| 一键 push + 发版 | `ENV_FILE=~/secrets/lingniao-prod.env make ship-cvm` |
| 仅远端发版 | `CVM_LOCAL_PREFLIGHT=1 ENV_FILE=... make release-cvm` |
| 打印 compose 片段（不 SSH） | `make cvm-deploy-dry-run` |
| U-1 beat 巡检 | `DEPLOY_HOST=ubuntu@IP make check-cvm-beat` |
| U-2 COS 真桶 | `COS_BUCKET=… COS_REGION=… COS_SECRET_ID=… COS_SECRET_KEY=… make check-cos-smoke` |
| U-3 域名 / TLS | `make check-weapp-domains` |
| U-4 支付回调 | `ENV=~/secrets/lingniao-prod.env make check-pay-callbacks` |

---

*文档变更：与 `release-cvm-on-server.sh`（脏 Git 门禁）、`make ship-cvm`（main-only）同步维护。*
