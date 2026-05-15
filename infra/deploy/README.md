# CVM / 微信小程序 HTTPS（Let's Encrypt）

快捷命令（仓库根目录）：`make issue-le-cert` · `make renew-le-cert` · `make sync-le-certs`。

**Git / 密钥单侧真源 / CVM 推荐 `make deploy-cvm-up`**：统一见 [**`docs/release-notes/CVM-canonical-deploy.md`**](../docs/release-notes/CVM-canonical-deploy.md)。

**已在 CVM shell 里登录（控制台 / SSH）要一键发版**：在仓库根执行 **`bash infra/deploy/release-cvm-on-server.sh`**（`git pull` + 全栈 compose build + `alembic upgrade head` + `nginx` 重启）；可选 **`USE_WECHAT_PAY_COMPOSE=1`** 叠加商户 PEM compose。

## 微信公众平台域名怎么填

微信开放平台 **`modify_domain` 接口示例**里，`requestdomain` / `uploaddomain` 等为 **`https://` 开头的完整项**，例如 `https://api.birdieai.cn`（见 [官方文档](https://developers.weixin.qq.com/doc/oplatform/openApi/OpenApiDoc/miniprogram-management/domain-management/modifyServerDomain.html)）。

- **公众平台网页后台**：若保存时提示「须 HTTPS」或拒绝纯主机名，请填 **`https://api.birdieai.cn`** 这类格式（**不要**带路径 **`/v1`**，也不要末尾多余的 `/`）。
- **DNS 预解析域名**是另一类配置，官方写明 **无需协议头**——勿与「服务器域名」混淆。

小程序代码里的 **`TARO_APP_API_BASE_URL`** 仍是接口根路径：`https://api.birdieai.cn/v1`。

## 为什么要换 Let's Encrypt

自签证书（`issuer` = 你自己）在 **微信真机 / 体验版** 上会触发 `request:fail errcode:-207`（Cronet 校验证书失败）。  
须使用 **公共 CA** 签发的证书（Let's Encrypt、腾讯云 SSL 等）。

## 推荐流程（本仓库已接好 webroot）

以下在 **CVM 仓库根目录**执行（且已配置 `.env.local`）。

### 1. 先用自签把栈拉起来（nginx 必须已在跑）

首次若没有证书文件，`make deploy-test` 会拒绝；先生成自签（可与 LE 共用域名）：

```bash
make test-certs HOST=api.birdieai.cn
make deploy-test
```

此时仍是自签，仅便于 curl / 运维；**小程序真机仍会报错**，继续下一步。

### 2. 申请 Let's Encrypt 并写入 nginx 挂载目录

```bash
make issue-le-cert EMAIL=你的邮箱@example.com DOMAIN=api.birdieai.cn
```

说明：

- 依赖 **Docker** 跑官方 `certbot` 镜像；
- 证书落在宿主机 **`/etc/letsencrypt`**，脚本会 **`sync` 到 `infra/test/certs/fullchain.pem` / `privkey.pem`** 并重载 nginx；
- **`infra/test/nginx.conf`** 固定读取上述两个文件名（与自签生成的同名文件兼容）。

调试可选用 staging（浏览器会提示不信任）：

```bash
CERTBOT_STAGING=1 make issue-le-cert EMAIL=… DOMAIN=api.birdieai.cn
```

### 3. 续约（与首次申请同一套 Docker certbot）

不要用宿主机 `certbot`（若未安装会踩坑）。在仓库根目录：

```bash
make renew-le-cert DOMAIN=api.birdieai.cn
```

等价：`bash infra/deploy/renew-le-cert-docker.sh api.birdieai.cn`

内部顺序：`docker … certbot renew` → **`make sync-le-certs`**（拷贝 PEM + `nginx -s reload`）。

**cron 示例**（每月两次，UTC 深夜错峰可自行调整）：

```cron
0 4 1,15 * * cd /opt/xiaoniao && make renew-le-cert DOMAIN=api.birdieai.cn >> /var/log/xiaoniao-certrenew.log 2>&1
```

### 4. 自检（仓库自带脚本）

```bash
make verify-weapp-https DOMAIN=api.birdieai.cn
# 要求健康检查必须通过时再开：
STRICT_HEALTH=1 make verify-weapp-https DOMAIN=api.birdieai.cn
```

等价：`bash infra/deploy/verify-weapp-https-readiness.sh api.birdieai.cn`

亦可手动：

```bash
openssl s_client -connect api.birdieai.cn:443 -servername api.birdieai.cn </dev/null 2>/dev/null \
  | openssl x509 -noout -issuer -subject
```

`issuer` 应为 Let's Encrypt（或 R3/E 系列中间），**不应**再是你自己的 `CN=api.birdieai.cn`。

### 6. 小程序报 uploadFile「trycloudflare / ngrok」主机

说明 **服务端 `.env.local` 里 `MINIO_PUBLIC_ENDPOINT` 仍指向本地穿透**。云服务器请到**仓库根目录**执行一键修正（会先备份 `.env.local`）：

```bash
cd /opt/xiaoniao   # 改成你在 CVM 上的实际路径
git pull           # 建议先拉最新代码拿到本脚本
bash infra/deploy/server-fix-minio-public.sh
docker compose --env-file .env.local restart backend
```

若不是 Docker、没有 `minio` 主机名，请手写 `MINIO_PUBLIC_ENDPOINT=http://127.0.0.1:9000` 或网关上的 `https://api.birdieai.cn/minio`，详见仓库根目录 **`.env.example`** 注释。

### 7. 上传 HTTP 403 / `InvalidAccessKeyId`

说明 **后端签名用的 `MINIO_ACCESS_KEY` 与 MinIO 容器里的 `MINIO_ROOT_USER` 不一致**。在仓库根目录执行自检脚本：

```bash
bash infra/deploy/check-minio-credentials-on-server.sh
```

按脚本提示对齐 `~/lingniao-golf/.env.local` 后 **`--force-recreate backend`**，并 **`docker restart xiaoniao-nginx`**。

### 8. 已有服务器仍是 server.crt / server.key（旧 nginx 配置）

若尚未生成 `fullchain.pem`，可先拷贝一次再起栈：

```bash
cp infra/test/certs/server.crt infra/test/certs/fullchain.pem
cp infra/test/certs/server.key infra/test/certs/privkey.pem
docker compose -f docker-compose.yml -f docker-compose.test.yml --env-file .env.local exec nginx nginx -s reload
```

### 9. CVM：`bind` 挂载 `backend`、Postgres 卷、健康检查（与 W8 Runbook 对齐）

更完整的步骤与排障表见 **[`docs/release-notes/W8-test-env-runbook.md`](../../docs/release-notes/W8-test-env-runbook.md)**。此处只列高频点：

| 主题 | 要点 |
|------|------|
| **非 git 部署** | 必须同步 **完整 `backend/`**（含 **`alembic/env.py`**、`script.py.mako`、`versions/*.py`），勿只拷 `app/` |
| **坏 `.venv` / `alembic` 导入失败** | 挂载 `./backend:/app` 时宿主机 `.venv` 会盖住镜像依赖；脚本 **`bash infra/deploy/cvm-rebuild-backend.sh`**（含 `sudo` 清理与 `uv sync`、`chown`） |
| **Postgres 口令** | **首次初始化**后改 `.env` **不会改变**库里密码；对齐旧口令或 **`docker compose down`** 后 **`docker volume rm …_postgres_data`** 再 `up`（**丢数据**） |
| **`502` + backend `Restarting`** | 先看 **`docker logs xiaoniao-backend`**，多为上述 DB / Alembic / 缺文件 |
| **健康检查 `405`** | `/v1/health` **仅 GET**；`curl -I` 走 **HEAD**，见 Runbook 「三（附）」 |
| **自检 .env** | 仓库根 **`make deploy-check-env ENV_FILE=.env.local`** |

### 10. （可选）`UV_LINK_MODE=copy`

在云盘/跨挂载装依赖时，`uv sync` 可能提示 hardlink 回退 copy。可 **`export UV_LINK_MODE=copy`** 或 Compose `run -e UV_LINK_MODE=copy …`，仅为消除告警，非故障。
