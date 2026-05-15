# CVM 规范化部署约定（Git + 单侧 env + 可选去挂载）

> 与对话中约定的「科学」运维方式一致：**代码只看 Git**，**密钥只在 Mac（或团队约定的一台）维护一份不入库**，**上线用 `scp`；代码同步永远不盖 `.env.local`**；可选 **`docker-compose.cvm.yml`** 去掉宿主机 bind，减少缺文件 / 跨平台 `.venv`。

**记号**：下文 **`$DEPLOY_REPO`** = CVM 上本仓库的路径（常与 `~/lingniao-golf` 一致）。

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

一键脚本（等价于：**§2 `git pull` + 上式 `up -d --build` + `alembic upgrade head` + `docker restart xiaoniao-nginx`**）：在仓库根 **`bash infra/deploy/release-cvm-on-server.sh`**（可选 **`USE_WECHAT_PAY_COMPOSE=1`**）。

或在本机仓库根（依赖 `.env.local` 与 Docker）：

```bash
make deploy-cvm-up
```

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

---

## 8. 运维坑：只重建 backend 后，HTTPS 上 `/v1/*` 全变 502

**现象**：`curl https://<域名>/v1/health` 为 **502**；Compose 里 **`xiaoniao-nginx`** 常为 **`unhealthy`**。  
**`docker exec xiaoniao-backend`** 内直连 **`http://127.0.0.1:8000/v1/health` 却是 200**；**`docker exec xiaoniao-nginx wget http://backend:8000/v1/health`** 也往往 200，但 **`docker exec xiaoniao-nginx wget --no-check-certificate https://127.0.0.1/v1/health`** 仍是 502。

**原因**：`infra/test/nginx.conf` 使用 **`proxy_pass http://backend:8000`**。在默认写法下 nginx 对工作进程侧的 **`backend` 主机名解析**会在加载配置（或 fork worker）阶段**固化**。**单独 `docker compose … --force-recreate backend`** 会使 **backend 容器 IP** 发生变化；若 **nginx 不复位**，仍会反代到**旧 IP**，出现 **upstream 连不上 → 502**。（Shell 在容器内执行 `wget http://backend:8000` 仍会走嵌入式 DNS **拿到新 IP**，故可与 nginx 502 **同时存在**。）

**处理**（任选其一）：

```bash
docker restart xiaoniao-nginx
```

或与其它服务一并重建 **nginx + backend**（若使用商户 PEM 叠层，续加 **`-f docker-compose.wechat-pay-key.yml`**）：

```bash
cd ~/lingniao-golf
docker compose -f docker-compose.yml -f docker-compose.test.yml -f docker-compose.cvm.yml \
  -f docker-compose.wechat-pay-key.yml \
  --env-file .env.local up -d --force-recreate nginx backend
```

未使用 **`docker-compose.wechat-pay-key.yml`** 时删掉对应 **`-f`** 即可。

**惯例**：日后每次 **仅重建 backend** 之后，**顺手 `docker restart xiaoniao-nginx`**，或 **成对 `--force-recreate nginx backend`**，可避免复现。

**根治（可选演进）**：在 `nginx.conf` 中配置 **`resolver 127.0.0.11 valid=10s`**，并用 **`set $upstream`** 变量包住 **`proxy_pass`**，使 **`backend`** 按需动态解析；（当前仓库仍用静态 `proxy_pass`，以运维惯例规避上述问题。）
