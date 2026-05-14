# CVM 规范化部署约定（Git + 单侧 env + 可选去挂载）

> 与对话中约定的「科学」运维方式一致：**代码只看 Git**，**密钥只在 Mac（或团队约定的一台）维护一份不入库**，**上线用 `scp`；代码同步永远不盖 `.env.local`**；可选 **`docker-compose.cvm.yml`** 去掉宿主机 bind，减少缺文件 / 跨平台 `.venv`。

**记号**：下文 **`$DEPLOY_REPO`** = CVM 上本仓库的路径（你与机器上常为 `~/lingnio-golf`，以实际为准）。

---

## 1. Mac：密钥「真源」

- 在 **仓库外**固定一份文件（示例路径，可自定）：
  - `~/secrets/lingniao-prod.env`（可复制仓库内 **`infra/deploy/env.prod.deployment.template`** 再填真值：`cp infra/deploy/env.prod.deployment.template ~/secrets/lingniao-prod.env`）
- 内容与线上一致，即 **`$DEPLOY_REPO/.env.local`** 的语义；**不要用带 `<...>` 的模板整块粘贴**。
- **不要**把该文件放进 Git；可用密码管理器 + 磁盘加密。

每次改密钥 / 域名 / 微信支付等：

```bash
scp ~/secrets/lingniao-prod.env ubuntu@YOUR_CVM:$DEPLOY_REPO/.env.local
ssh ubuntu@YOUR_CVM 'cd ~/lingnio-golf && docker compose -f docker-compose.yml -f docker-compose.test.yml -f docker-compose.cvm.yml --env-file .env.local up -d --force-recreate backend celery-worker'
```

（请将 `~/lingnio-golf` 改成你的 **`$DEPLOY_REPO`**；Mac 本地 shell 可先 `export DEPLOY_REPO=/home/ubuntu/lingnio-golf`。）

成功后 **从服务器拉回备份**（灾备）：

```bash
mkdir -p ~/secrets/backups && scp "ubuntu@YOUR_CVM:$DEPLOY_REPO/.env.local" "~/secrets/backups/lingniao-env-$(date +%Y%m%d-%H%M).bak"
chmod 600 ~/secrets/backups/*.bak ~/secrets/lingniao-prod.env
```

---

## 2. 代码：`git`，不用「散装 rsync」当主干

CVM：

```bash
cd ~/lingnio-golf
git remote -v
git fetch origin && git checkout main && git pull --ff-only
# 或发版：`git checkout vX.Y.Z`
```

Mac 若要 rsync：**必须** `--exclude '.env.local'`，且 **不要盲目 `--delete`** 盖掉服务端树。

---

## 3. 启栈：`docker-compose.cvm.yml`（推荐）

```bash
cd ~/lingnio-golf
docker compose -f docker-compose.yml -f docker-compose.test.yml -f docker-compose.cvm.yml --env-file .env.local up -d --build
```

或：

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
```
