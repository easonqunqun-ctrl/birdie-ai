# CVM 规范化部署约定（Git + 单侧 env + 可选去挂载）

> 与对话中约定的「科学」运维方式一致：**代码只看 Git**，**密钥只在 Mac（或团队约定的一台）维护一份不入库**，**上线用 `scp`；代码同步永远不盖 `.env.local`**；可选 **`docker-compose.cvm.yml`** 去掉宿主机 bind，减少缺文件 / 跨平台 `.venv`。

**顺滑发版（踩坑与命令表）**：[`cvm-release-smooth-runbook.md`](cvm-release-smooth-runbook.md)。

**记号**：下文 **`$DEPLOY_REPO`** = CVM 上本仓库的路径（常与 `~/lingniao-golf` 一致）。

---

## −1. 本地 Compose vs CVM Compose（关键差异速查）

> 本地 `make up` 跑得动 ≠ 生产同款跑得动。下表列出 **本地** 与 **CVM 生产形态** 在容器集合 / 卷 / 网络 / 外部依赖上的实际差异，用于发版前对照。
> 配套巡检：[`cvm-release-smooth-runbook.md`](cvm-release-smooth-runbook.md) **§七·补**（U-1～U-4 命令表）。

| 维度 | 本地 (`make up`) | CVM 测试栈 (`make deploy-test` / `deploy-cvm-up`) | 生产 (W9 后) |
|------|--------------------|---------------------------------------------------|--------------|
| Compose 文件 | `docker-compose.yml` | `+ docker-compose.test.yml + docker-compose.cvm.yml [+ docker-compose.wechat-pay-key.yml]` | 同 CVM 测试栈；按需删 `docker-compose.test.yml` 中的开发用映射 |
| 容器集合 | `backend / celery-worker / celery-beat / ai_engine / postgres / redis / minio` | 同左 **+ nginx** | 同左；可选移除 minio 改 COS |
| 对外入口 | `backend:8000` 直暴 / minio:9000 直暴 | **nginx 终结 TLS**，反代 `/v1` → backend、`/minio/*` → minio | 同 CVM；证书必须公有 CA |
| `.env` 来源 | 仓库根 `.env.local`（开发占位符） | CVM **服务器上**的 `.env.local`（生产凭据，不入 Git） | 同 CVM；W9 加 `WECHAT_PAY_*` 真值与 COS 凭据 |
| 微信支付 PEM | mock (`WECHAT_PAY_MOCK_MODE=true`) | 同 mock，除非 `docker-compose.wechat-pay-key.yml` 挂载 | 必须挂载真 `apiclient_key.pem` 且 mock=false |
| 对象存储 | MinIO（容器内 `minio:9000`，公网 `localhost:9000`） | MinIO（公网走 `https://<host>/minio/*` 经 nginx） | **COS**（`STORAGE_PROVIDER=cos`，桶 + CDN 真域） |
| LLM | mock (`LLM_MOCK_MODE=true`) | 可 mock 或接 DeepSeek 真 key | DeepSeek 真 key + 预算 |
| AI 引擎 | mock_pipeline.py | mock 或 real_pipeline.py（按 `AI_ENGINE_MOCK_MODE`） | real_pipeline.py（依赖 MediaPipe + 真桶视频） |
| Celery beat | 容器内运行（同 worker 镜像） | 同左；**需 `docker ps` 实测在线** | 同左 + 监控告警 |
| 微信登录 | mock (`WECHAT_MOCK_LOGIN=true`) | false，走真实 `wx.login`（W8-T4） | false |
| 配额 | `QUOTA_MODE=` 取默认（受限） | `QUOTA_MODE=unlimited`（W8-T3 测试期） | 按业务恢复受限 |
| 公网证书 | 自签 / 跳过 | 自签或 Let's Encrypt | **必须 Let's Encrypt / 公有 CA** |
| 关键变量差异 | `APP_ENV=development` | `APP_ENV=staging` | `APP_ENV=production` |
| 运维入口 | `make up` / `make logs` | `make deploy-cvm-up` / `make deploy-cvm-ps` / `make deploy-cvm-logs` | `make ship-cvm` / `make release-cvm` |

发版前 **U-1～U-4** 命令表见 [`cvm-release-smooth-runbook.md`](cvm-release-smooth-runbook.md) **§七·补**。

---

## 0. 过渡期：本次不走服务端 Git（rsync），下次再切 Git

若 CVM 上 **没有 `.git`**、代码靠 **`infra/deploy/publish-backend-to-cvm.sh`** 同步：**默认**用 **`scp`** 将仓库根的 **`docker-compose.yml`**、**`docker-compose.test.yml`**、**`docker-compose.cvm.yml`** 推到 **`$DEPLOY_REPO/`**，再 **rsync** **`backend/`** 与 **`ai_engine/`**，本节为**唯一推荐主干链路**（与 **`docs`** 正文 §2 「代码只看 Git」冲突时，**以你正处于的阶段为准**：过渡完成后再删掉本节依赖）。

### 本期须「打通」的五件事（减少接口/链路类事故）

1. **单会话构建**：仅在 **CVM `tmux`**（或 **一条**长 SSH）里跑 **`docker compose … up -d --build backend celery-worker ai_engine`**；不要同时开多条 `up --build` / 多余的 `compose build …`。
2. **本机发版**：仓库根 **`SSH_BATCH_MODE=yes make publish-backend-cvm`**（脚本：**scp compose 三件套** + **SSH keepalive** + rsync **backend + ai_engine**、远端 **compose build** + **alembic**）；长构建仍可能久，**断线则上服务器 `tmux attach`** 看是否还在跑，不要立刻再叠第二条。云上确需自备 compose：**`REMOTE_RSYNC_COMPOSE=no`**（少用）。
3. **迁移**：发版后确认 **`alembic upgrade head`** 成功（脚本默认会跑）；线上 500 先核对 **迁移版本 vs 代码**。
4. **三件套同事到场**：backend / celery / **ai_engine** 同一轮构建或同一脚本带齐（避免只更后端、推理仍旧）。
5. **收尾**：compose 成功后 **`docker restart xiaoniao-nginx`**（脚本已尝试）；仍有域名侧问题见本文 **§8**。
6. 与发版链路 **并行** 的工程排期见 **`release-notes/parallel-engineering-backlog.md`**。

### 发版与排障口令（O2 · Runbook 摘要）

> 完整思想与 nginx 502 说明见本文 **§8**；与 **[`parallel-engineering-backlog.md`](parallel-engineering-backlog.md)** P1·O2 互链。

| 场景 | 建议命令（在 CVM SSH 内） |
|------|---------------------------|
| 恢复发版终端 | `tmux attach -t deploy`（会话名按你实际为准） |
| 是否仍在 build / `uv sync` | `pgrep -af 'uv sync\|docker-compose compose.*lingniao-golf'` |
| 业务容器状态 | `cd $DEPLOY_REPO && docker compose -f docker-compose.yml -f docker-compose.test.yml -f docker-compose.cvm.yml $(test -f docker-compose.wechat-pay-key.yml && echo '-f docker-compose.wechat-pay-key.yml') --env-file .env.local ps` |
| DB 迁移版本 | `docker compose … exec backend uv run alembic current`（与 `upgrade head` 同一套 `-f` / `--env-file`） |
| 清理重复 compose 客户端（慎） | 见 backlog **P1·O1** 整理说明；优先 **只留一条** `up -d --build`，勿与业务窗口抢 BuildKit |
| 回滚思路 | 无 Git 时以 **上一版镜像 tag / 宿主机备份树** 为准；至少保留可工作的 `docker compose … up -d` 一条命令与 `.env.local` 备份 |

### 环境变量速查（O3 · MinIO / AI 引擎 / 存储）

| 变量（示例） | 角色 | 说明 |
|--------------|------|------|
| `MINIO_ENDPOINT` | 容器内 S3 API | backend / ai_engine **内网**访问，如 `http://minio:9000` |
| `MINIO_PUBLIC_ENDPOINT` | 对外 URL 基准 | 小程序直传、浏览器；占位时 backend 可回退到 `API_PUBLIC_BASE_URL/minio`（见 `config.effective_minio_public_endpoint`） |
| `STORAGE_PROVIDER` | `minio` / `cos` | 决定对象存储实现分支 |
| `AI_ENGINE_URL` | HTTP | Celery / backend 调推理，如 `http://ai_engine:9000` |
| **ai_engine 拉分析视频** | — | 公网 `video_url` 在 **[`ai_engine/app/pipeline/preprocess.py`](../../ai_engine/app/pipeline/preprocess.py)** 中优先改写为内网 `MINIO_ENDPOINT` 再 `curl`，避免容器内访问不到公网网关。 |

### Celery Beat（订单超时关单）

- 任务 **`xiaoniao.expire_stale_pending_orders`** 写入 **`backend/app/celery_app.py`** `beat_schedule`（默认 15min）— **必须跑 `celery beat` 调度进程**才会执行；仅 `worker` 不会触发周期任务。
- 本地：**`docker-compose.yml`** 内含 **`celery-beat`** 服务（镜像与 worker 同为 backend）；`make up` 若省略该服务请加：  
  `docker compose --env-file .env.local up -d celery-beat`
- **CVM**：与 worker 一起在 compose 叠叠乐时 **务必勾选/包含 celery-beat 一条**；发布后 `docker ps | grep celery` 应具备 `beat`。

#### 日常巡检（U-1 紧急队列）

> 一次性核验「容器在 + 近 30 分钟有派发 + 阈值生效」，对应 [`docs/19-产品开发迭代计划-当前队列.md`](../19-产品开发迭代计划-当前队列.md) **§二 U-1**。

```bash
# 默认走远端 CVM（与 publish-backend-cvm 同一对 SSH 密钥/Host/项目路径）
make check-cvm-beat

# 本机 compose 栈（开发环境复现）
LOCAL=1 make check-cvm-beat

# 自定义远端
DEPLOY_HOST=ubuntu@1.2.3.4 DEPLOY_REPO=/home/ubuntu/lingniao-golf \
  BIRDIE_CVM_KEY=$HOME/.ssh/id_ed25519_birdie_golf \
  make check-cvm-beat

# 失败诊断：放宽窗口看更长历史
SINCE=2h make check-cvm-beat
```

脚本三段输出对应：

1. `docker compose ps celery-beat` —— 是否 `Up/running`
2. `docker compose logs --since ${SINCE} celery-beat` —— 是否抓到 `expire_stale_pending_orders` / `xiaoniao.expire_stale_pending_orders`
3. `docker compose exec backend python -c "from app.config import settings; print(settings.PAYMENT_PENDING_ORDER_EXPIRE_MINUTES)"` —— 阈值（默认 `120`，`≤0` 关闭超时回收）

### 从 §0 rsync → 本节 Git 主干（一键迁移）

已落地文档与脚本；**在云服务器 SSH 执行**（变量换成你的远端地址即可）：

- **步骤全文**：[**`docs/release-notes/CVM-migrate-rsync-to-git.md`**](CVM-migrate-rsync-to-git.md)
- **脚本**：**`infra/deploy/cvm-bootstrap-git-on-server.sh`**（需 **`GIT_REPO_URL`**）

完成后：**§2 「代码：`git`** 生效；Mac：**`git push` → `make release-cvm`**。**`publish-backend-cvm`** 仅作兜底。

### 下一版切 Git 时最小改动清单（摘要）

1. Mac：确认 **`origin`** 有可跟踪分支 / tag，并完成首次 **`git push`**。
2. CVM：按 **`CVM-migrate-rsync-to-git.md`** 跑 bootstrap；或以脚本自动 **`mv` 备份 + `git clone`** 恢复原路径 **`$DEPLOY_REPO`**。
3. 发版：优先 **`bash infra/deploy/release-cvm-on-server.sh`**（等价 **`git pull` + compose + alembic**）；不再需要 rsync compose 也可用 **`make release-cvm`**。
4. 客户端：`client/.env.production` 与 **同一 Git 提交**打包（沿用本文 **§6**）。
5. 记录：**tag + 简短 release 说明**，便于对照线上接口契约。

---

## 1. Mac：密钥「真源」

- 在 **仓库外**固定一份文件（示例路径，可自定）：
  - `~/secrets/lingniao-prod.env`（可复制仓库内 **`infra/deploy/env.prod.deployment.template`** 再填真值：`cp infra/deploy/env.prod.deployment.template ~/secrets/lingniao-prod.env`）
- 内容与线上一致，即 **`$DEPLOY_REPO/.env.local`** 的语义；**不要用带 `<...>` 的模板整块粘贴**。
- **不要**把该文件放进 Git；可用密码管理器 + 磁盘加密。

每次改密钥 / 域名 / 微信支付等：

```bash
scp ~/secrets/lingniao-prod.env ubuntu@YOUR_CVM:$DEPLOY_REPO/.env.local
ssh ubuntu@YOUR_CVM "cd ~/lingniao-golf && docker compose -f docker-compose.yml -f docker-compose.test.yml -f docker-compose.cvm.yml --env-file .env.local up -d --force-recreate backend celery-worker"
```

（**`scp` 左边的 `$DEPLOY_REPO`** 须在 **Mac** 本地先 `export`；若服务端仓库不在 `~/lingniao-golf`，把第二条里的路径改成 **`$DEPLOY_REPO` 服务端同款路径**。）

成功后 **从服务器拉回备份**（灾备）：

```bash
mkdir -p ~/secrets/backups && scp "ubuntu@YOUR_CVM:$DEPLOY_REPO/.env.local" "~/secrets/backups/lingniao-env-$(date +%Y%m%d-%H%M).bak"
chmod 600 ~/secrets/backups/*.bak ~/secrets/lingniao-prod.env
```

---

## 2. 代码：`git`，不用「散装 rsync」当主干

> **当前 CVM 暂无 `.git`** 时，过渡期以 **§0** 为准；待 clone 后再回到本节。

CVM：

```bash
cd ~/lingniao-golf
git remote -v
git fetch origin && git checkout main && git pull --ff-only
# 或发版：`git checkout vX.Y.Z`
```

Mac 若要 rsync：**必须** `--exclude '.env.local'`，且 **不要盲目 `--delete`** 盖掉服务端树。

---

## 3. 启栈：`docker-compose.cvm.yml`（推荐）

```bash
cd ~/lingniao-golf
docker compose -f docker-compose.yml -f docker-compose.test.yml -f docker-compose.cvm.yml --env-file .env.local up -d --build
```

一键脚本（等价于：**§2 `git pull` + 上式 `up -d --build` + `alembic upgrade head` + `docker restart xiaoniao-nginx`**）：在仓库根 **`bash infra/deploy/release-cvm-on-server.sh`**（若存在 **`docker-compose.wechat-pay-key.yml`** 会自动叠加；**`WECHAT_PAY_MOCK_MODE=false`** 时会先执行 **`infra/deploy/check-cvm-pay-mount.sh`**）。服务端若尚无 **`.git`**（仅 rsync 代码）：**`SKIP_GIT=1 bash infra/deploy/release-cvm-on-server.sh`**。

或在本机仓库根（依赖 `.env.local` 与 Docker）：

```bash
make deploy-cvm-up
```

**真实微信支付**：`.env.local` 里 **`WECHAT_PAY_MOCK_MODE=false`** 时，须同时在仓库根维护 **`docker-compose.wechat-pay-key.yml`**（将宿主 **`apiclient_key.pem`** 挂入 backend，模板见 **`docker-compose.wechat-pay-key.example.yml`**）。**`make deploy-cvm-up`** 会先跑 **`make deploy-check-cvm-pay`**；后端也会在启动阶段校验 **`WECHAT_PAY_CERT_PATH` 在容器内可读**，避免「进程起了但下单 502」。

**AI 对话**：发版后用 **`curl -sS https://<域名>/v1/health`** 确认 **`redis"`/`"database"` 均为 `ok`**；**.env.local** 勿留 **`LLM_API_KEY`** 占位；网关对 **`/v1/`** 须关闭 **`proxy_buffering`**（本仓库 **`infra/test/nginx.conf`** 已按 SSE 配置）。

**效果**：backend / celery / ai_engine **不绑定**宿主 `./backend`、`./ai_engine`，避免「宿主缺 alembic、坏 .venv」；**代价**：改代码后要 **`docker compose … build`** 才能进容器。

本地开发 **不要** 默认加这层文件（仍可用 `make up` / `make deploy-test`）。

---

## 4. `infra/deploy/cvm-rebuild-backend.sh`

只要 **必须** 重 build `backend`/`celery` 且与 `make deploy-cvm-up` 使用 **同一套 `-f`** 时再用本脚本；更简单时直接 **`make deploy-cvm-up`**。

未使用 cvm 叠层时：**`bash infra/deploy/cvm-rebuild-backend.sh`**

已使用 **`docker-compose.cvm.yml`**：

```bash
USE_DOCKER_COMPOSE_CVM_LAYER=1 bash infra/deploy/cvm-rebuild-backend.sh
```

脚本会在该模式下自动 **`FIX_HOST_BACKEND_VENV=0`**、**`SKIP_BACKEND_TREE_CHECK=1`**（无宿主 bind / 不再要求 `backend/alembic` 在磁盘上完整）。

---

## 5. TLS：Let’s Encrypt 与 `infra/test/certs`

- 签发在 **`/etc/letsencrypt/live/<域名>/`**；
- nginx 挂载的是 **`infra/test/certs/fullchain.pem` / `privkey.pem`**，** renew 后要再同步**，见 `infra/deploy/README.md`、`make sync-le-certs`。

---

## 6. 小程序发包

客户端 **`client/.env.production`** 与后端 **同一 Git 提交**：

```bash
make client-build-weapp-prod
```

公众平台 **服务器域名**：`request`（及 uploads）填 **`https://api.birdieai.cn`** 等真实主机，参见 `docs/release-notes/go-live-weapp-fool-checklist.md`。

---

## 7. 发版自检（最短）

```bash
curl -sS https://api.birdieai.cn/v1/health | head -c 200
openssl s_client -connect api.birdieai.cn:443 -servername api.birdieai.cn </dev/null 2>/dev/null | openssl x509 -noout -issuer
docker compose -f docker-compose.yml -f docker-compose.test.yml -f docker-compose.cvm.yml --env-file .env.local exec backend env | grep '^WECHAT_MINIPROGRAM'
docker compose -f docker-compose.yml -f docker-compose.test.yml -f docker-compose.cvm.yml --env-file .env.local exec backend env | grep '^WECHAT_PAY'
```

### 7.1 脚手架：`scripts/deploy-cvm.sh` 与 `scripts/cvm-smoke.sh`

- **阶段清单（本机可读，不占 SSH）**：`bash scripts/deploy-cvm.sh`；等价 **`make cvm-deploy-help`**。
- **打印建议在 CVM 执行的 compose / curl（不 SSH）**：`bash scripts/deploy-cvm.sh --dry-run` → **`make cvm-deploy-dry-run`**。
- **懒人一条（推荐日常）**：本机先 **`git push`**，再在仓库根 **`make release-cvm`**（等同 **`bash scripts/cvm-remote-release.sh`**；云上 **`release-cvm-on-server.sh`** 读 **`$DEPLOY_REPO/.env.local`**，不负责在 Mac 上配 **`ENV_FILE`**）。
- **本机一条龙（稳妥）**：**`make cvm-stable-from-mac ENV_FILE=~/secrets/…`**（先做 **`cvm-preflight`**，再 **`verify-weapp-https`**（可 **`SKIP_TLS=1`** 跳过），再 **`cvm-remote-release`**）；只演练不切 SSH：**`DRY_RUN=1`**。
- **一键预检 Makefile**：推荐 **`make cvm-preflight`**；等价 **`make cvm-env-preflight`** / `deploy-cvm.sh --local-preflight`（占位符 + **真实支付** compose 挂载检查）。
- **预检后继续测公网 TLS**：**`make cvm-preflight-tls`**（先 `cvm-preflight`，再 `verify-weapp-https`，`DOMAIN` 默认 `api.birdieai.cn`）。
- **代码已在远端**：本机 **`make cvm-remote-release`** 或 **`bash scripts/cvm-remote-release.sh`**（SSH 执行 `infra/deploy/release-cvm-on-server.sh`；可调 `SKIP_GIT=1` / `GIT_BRANCH=` / `DEPLOY_HOST=`）。可选 SSH 前先跑与 **`--local-preflight`** 相同的两段检查：**`CVM_LOCAL_PREFLIGHT=1 ENV_FILE=~/secrets/…`**。
- **HTTPS 冒烟**：`DOMAIN=api.birdieai.cn bash scripts/cvm-smoke.sh`；带 JWT：`TOKEN='<paste>' bash scripts/cvm-smoke.sh`；可选：`LOGIN_CODE=…`。→ **`make cvm-smoke DOMAIN=… TOKEN=…`**。

**`infra/deploy/release-cvm-on-server.sh`**：若服务端 **暂无 `.git`**（rsync-only 过渡期），可先 **`SKIP_GIT=1 bash infra/deploy/release-cvm-on-server.sh`**（仍会跑 compose · alembic · nginx）。

---

## 8. 运维坑：Compose 重建容器后 nginx 仍指向旧 IP → `/v1/*` 或 `/minio/*` 502

**现象**：`curl https://<域名>/v1/health` 或 **`wx.uploadFile` 直传存储**返回 **502 Bad Gateway**（HTML 页常为 nginx）；Compose 里 **`xiaoniao-nginx`** 可能 **`healthy`**（因其自检只打 **`backend:8000`**，不经 HTTPS）。  
**`docker exec xiaoniao-backend`** 内直连 **`http://127.0.0.1:8000/v1/health` 却是 200**；**`docker exec xiaoniao-nginx wget http://backend:8000/v1/health`** 也往往 200，但 **`curl https://<域名>/v1/health`** 仍是 502。

**原因**：旧版 nginx 配置使用 **`proxy_pass http://backend:8000`** / **`http://minio:9000`** 时，对工作进程侧的 **`backend` / `minio` 主机名解析**可能在加载配置阶段**固化**。**单独 `docker compose … --force-recreate backend`**（或重建 **minio**）会使 **容器 IP** 发生变化；若 **nginx worker 不复位**，仍会反代到**旧 IP**，出现 **upstream 连不上 → 502**。Shell 在容器内执行 **`wget http://backend:8000`** 仍会走嵌入式 DNS **拿到新 IP**，故可与 nginx 502 **同时存在**。小程序上传走 **`/minio/`**，重建 MinIO 后同样会触发。

**根治（仓库已落地）**：`infra/test/nginx.conf` 在 **443 server** 内配置了 **`resolver 127.0.0.11 valid=10s`**，并对 **`/v1/`**、**`/minio/`** 使用 **`proxy_pass http://$backend_host:8000`** / **`http://$minio_host:9000$uri`**（`/minio/` 在 **`rewrite … break`** 之后拼接 **`$uri`**），按请求解析上游，避免 stale IP。

**仅 `docker compose ps` 标记 nginx `unhealthy`**：若公网 **443 已可** `curl /v1/health`，多为 **backend 冷启动**长于健康检查 **`start_period`**。用 **`docker inspect xiaoniao-nginx --format '{{json .State.Health}}'`** 看最近 `Log`。`docker-compose.test.yml` 已将 nginx 自检 **`start_period`** 提到 **90s** 并略放宽 `interval/timeout`（仍探测 `http://backend:8000/v1/health`）。

### 8.2 `nginx` 健康检查「假不健康」的常见误判（false positive）

以下为 **Compose 语义上的 healthy/unhealthy**，与上文 **HTTPS 对用户已可用但 worker 上游 IP 陈旧**（真 502）区分：

| 现象 | 可先当「误判」处理的条件 | 下一步 |
|------|--------------------------|--------|
| **`ps` 中 nginx `(unhealthy)`** | **`curl -sf https://<域名>/v1/health`** 已返回 **`"status"`** JSON，且 **`services.database/redis`** 在健康检查里也为 ok | **健康检查探测窗口**：仅等满 **`start_period`** 后再看一眼；仍为 unhealthy 多数是 **阈值过紧**：一次超时即失败。**`docker inspect xiaoniao-nginx --format '{{json .State.Health.Log}}'`** 若多为 **timeout/connect**，可在叠层 compose 略增大 **`interval`/`timeout`**，或确认 **后端启动时间变长（迁移/预热）**。 |
| **nginx healthy 但公网间歇 502** | 与用户侧 **同一时间** **`docker exec xiaoniao-nginx`** 内设变量反代 **`/v1/health`** 也失败 | 优先按 **§8 根治段**：`resolver + $backend_host`，并 **`docker restart xiaoniao-nginx`** 或 **`--force-recreate nginx`**。 |

**不要将 `depends_on.service.condition: service_healthy` 的失败**笼统当成「网关坏了」：若 **仅是 nginx 自检偶发超时**，可改为 **`service_started`** 或放宽检查后 **仍用外网 `/v1/health`** 作主验收。

**处理**（仍建议在合并 nginx.conf 变更后执行一次，或旧镜像未更新时兜底）：

```bash
docker restart xiaoniao-nginx
```

或与其它服务一并重建 **nginx + backend + minio**（若使用商户 PEM 叠层，续加 **`-f docker-compose.wechat-pay-key.yml`**）：

```bash
cd ~/lingniao-golf
docker compose -f docker-compose.yml -f docker-compose.test.yml -f docker-compose.cvm.yml \
  -f docker-compose.wechat-pay-key.yml \
  --env-file .env.local up -d --force-recreate nginx backend minio
```

未使用 **`docker-compose.wechat-pay-key.yml`** 时删掉对应 **`-f`** 即可。

**惯例**：若服务器尚未 **`git pull`** 拿到上述 nginx 变更，日后每次 **仅重建 backend / minio** 之后，仍可 **`docker restart xiaoniao-nginx`** 兜底。
