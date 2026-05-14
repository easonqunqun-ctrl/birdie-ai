# W8 测试环境部署 Runbook

> **规范化部署（Git + 密钥真源 + `docker-compose.cvm.yml`）**：见 **`docs/release-notes/CVM-canonical-deploy.md`**。
>
> **目标**：让一台干净的腾讯云 / 阿里云 CVM（Ubuntu 22.04，2C4G+，公网 IP）从零跑起完整的「小鸟 AI」测试环境，让微信开发者工具能扫预览码、真机走通核心闭环。
>
> **适用范围**：W8 内测期。**不**涉及 ICP 备案、微信支付商户号、正式域名/证书——这些留给 W9。
>
> **前置准备**：
> - 一台 CVM，公网 IP 已记下（下文用 `$HOST` 代指；可以是 IP 或解析到这个 IP 的域名）
> - SSH 私钥，能 `ssh ubuntu@$HOST`
> - 微信小程序后台已经拿到 `AppID` 和 `AppSecret`（公众平台 → 开发管理 → 开发设置）
> - DeepSeek API key（或其他 LLM 供应商）

---

## 一、CVM 装 Docker（5 分钟）

```bash
# 1) SSH 进 CVM
ssh ubuntu@$HOST

# 2) 装 docker + docker compose plugin
sudo apt-get update
sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
    -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
  https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io \
    docker-buildx-plugin docker-compose-plugin

# 3) 把当前用户加进 docker 组（免 sudo）
sudo usermod -aG docker $USER
newgrp docker  # 当前 shell 立即生效

# 4) 自检
docker compose version  # 期望 v2.x
```

---

## 二、拉代码 + 配 .env.local

```bash
cd /opt
sudo mkdir -p xiaoniao && sudo chown -R $USER:$USER xiaoniao
cd xiaoniao

# 用 deploy key 或 https + token 拉代码（以下为示意，改成你的远端地址）
git clone git@github.com:YOUR_ORG/YOUR_REPO.git .
git checkout main  # 或对应 W8 标签

# 复制测试模板，按提示填值
cp .env.test .env.local
nano .env.local
```

### 若非 git：`rsync`/手工拷贝目录

部分 CVM **没有 `.git`**，代码靠开发机同步。此时必须把整个仓库（至少 **`backend/` 全目录**、`docker-compose*.yml`、`infra/`、`alembic.ini`）对齐到线上同一目录。**不要**只同步 `backend/app/`，否则会缺 **`backend/alembic/env.py`**、**`script.py.mako`**、`versions/` 不全，Alembic 直接失败。**不要**把 Mac 上的 **`backend/.venv`** rsync 到 Linux（架构/路径都不同）；线上由 Docker 镜像 + 挂载目录内 `uv sync` 或由脚本处理（见第六节）。

**推荐运维命令（仓库根、与 compose 同目录）：**

```bash
make deploy-check-env ENV_FILE=.env.local
bash infra/deploy/cvm-rebuild-backend.sh      # 含：sudo 清坏 .venv、compose run 内 uv sync、重建 backend/celery
```

**`.env.local` 云上必改项**（不要使用带尖括号的 `<change-me-*>`——历史上易被整段粘进运行时；若编辑器里还能看到 `<your-` 则说明未替换干净）：

| 变量 | 说明 |
|---|---|
| `APP_SECRET_KEY` / `JWT_SECRET_KEY` | `python3 -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `API_PUBLIC_BASE_URL` | 必须与 Nginx HTTPS 网关对外主机一致（如 `https://api.example.com`） |
| `POSTGRES_PASSWORD` | 同上随机串（**两处**：本变量 + `DATABASE_URL` 中密码段落须一致） |
| `BACKEND_CORS_ORIGINS` | 含预览 / 小程序相关 Origin（可逗号多条） |
| `MINIO_PUBLIC_ENDPOINT` | 一般 `https://与 API 同源主机/minio`，且须与网关反代路由一致 |
| `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` | **须与 compose 起来的 MinIO 容器 ROOT 凭证一致**（单机默认常为 `minioadmin`/`minioadmin`；勿填与镜像初始化无关的假 AK） |
| `REDIS_URL` | 镜像内 Redis 无口令时使用 `redis://redis:6379/0`，与 `.env.test` 默认一致即可 |
| `WECHAT_MINIPROGRAM_APPID` | 微信公众平台 → AppID |
| `WECHAT_MINIPROGRAM_SECRET` | 同上 → AppSecret |
| `LLM_API_KEY` | DeepSeek（或其它供应商）控制台；留空则为 FakeLLM 告警 |

**默认已经配好不用动的关键开关**：

```dotenv
APP_ENV=staging
WECHAT_MOCK_LOGIN=false   # ← 启用真实 wx.login（W8-T4 重点）
QUOTA_MODE=unlimited      # ← 内测不卡免费配额（W8-T3 重点）
WECHAT_PAY_MOCK_MODE=true # ← 支付仍 mock，前端 PAYMENT_ENABLED=false
```

---

## 三、生成自签 HTTPS 证书 + 起栈

```bash
# 在 /opt/xiaoniao 目录
make test-certs HOST=$HOST    # 例：make test-certs HOST=test.birdieai.example.com
make deploy-test
```

`make deploy-test` 做的事：
1. 拉/构建 6 个镜像：`postgres / redis / minio / backend / celery-worker / ai_engine / nginx`
2. backend 启动时跑 `alembic upgrade head` 建表
3. minio 自动建 bucket `xiaoniao-videos-test` 并开匿名读
4. nginx 监听 80/443：TLS 证书固定读 **`infra/test/certs/fullchain.pem`** + **`privkey.pem`**（`make test-certs` 会从自签 `server.crt`/`server.key` 同步这两个文件名）

**微信小程序真机 / 体验版**不能接受自签 HTTPS（会出现 `errcode:-207`）。线上请在栈跑起来后用 **`make issue-le-cert EMAIL=…`** 换 Let's Encrypt，详见 **`infra/deploy/README.md`**。

**等 30~60s 后**，确认服务都起来了：

```bash
make test-ps
# 期望 7 个容器全部 Up，nginx 健康检查 healthy

make test-health HOST=$HOST
# 期望：✓ /v1/health 返回 200（GET；勿用 curl -I，HEAD 会 405）
```

---

## 三（附）、健康检查与 TLS 探活

- **`/v1/health` 仅支持 GET**。`curl -I` / `curl --head` 发的是 **HEAD**，后端会 **405 Method Not Allowed**（响应里 `Allow: GET`），**不代表**服务挂了。
- 推荐：`curl -sk https://$HOST/v1/health`（或 `make test-health HOST=$HOST`，内部为 GET）。

---

## 四、CVM 安全组 / 云防火墙

腾讯云控制台 → 安全组 → 入站规则，**至少**放行：

| 端口 | 来源 | 备注 |
|---|---|---|
| `22/tcp` | 你的办公 IP | SSH |
| `443/tcp` | `0.0.0.0/0` | 业务 HTTPS |
| `80/tcp` | `0.0.0.0/0` | 跳转用（也方便后续 Let's Encrypt） |

**不要**放行 `8000` / `9000` / `9001` / `5432` / `6379`——这些都被 nginx 兜起来了，公网暴露 = 数据库被人拖。MinIO Console（容器内 9001）在测试栈只映射到 **`127.0.0.1:9002`**（避免与主机上其它 `9001` 占用冲突），需要 `ssh -L 9002:127.0.0.1:9002 ubuntu@$HOST` 转发到本机访问。

---

## 五、客户端配置 + 微信开发者工具预览

### 5.1 在本地开发机（不是 CVM 上！）

```bash
cd client
cp .env.test .env.test.local       # local 不入仓
echo "TARO_APP_API_BASE_URL=https://$HOST/v1" >> .env.test.local
pnpm build:weapp:test              # 输出到 client/dist/
```

### 5.2 微信开发者工具

1. 打开「微信开发者工具」→ 导入 **`client` 目录**（含 `project.config.json`，`miniprogramRoot` 为 `dist/`），AppID 填真实那个
2. 设置 → 项目设置 → **「不校验合法域名、web-view（业务域名）、TLS 版本以及 HTTPS 证书」勾上**（自签证书必需）
3. 设置 → 项目设置 → 调试基础库 ≥ `2.27.1`
4. 工具栏「预览」→ 用绑定为开发者/体验者的微信扫码

### 5.3 真机首次登录走查

| 步骤 | 期望表现 |
|---|---|
| 扫码进入小程序 | 直接落到「同意条款」页（W8-T1） |
| 同意条款 → 自动调 wx.login | 后端 logs 看到 `wechat_code2session` 命中**真实**分支（不是 mock） |
| `users` 表新增一行 | `wechat_openid` 是真 openid（30 字符 base64），不是 `mock_openid_xxx` |
| 完成 onboarding | 落到 tabBar 首页 |
| 顶部右上角有 `STAGING` 角标 | 来自 `EnvBadge`（`APP_ENV=staging`） |
| 拍 5 段挥杆视频 | 都能成功提交分析（不会被卡 3 次月限） |

CVM 上看后端日志：

```bash
make test-logs        # 全部
# 或只看 backend
docker compose -f docker-compose.yml -f docker-compose.test.yml logs -f backend
```

---

## 六、常见踩坑

| 现象 | 原因 | 处理 |
|---|---|---|
| **502**，nginx 正常；`xiaoniao-backend` **Restarting** | 后端启动命令里 **Alembic 失败** 或 **uvicorn 未起来** | `docker logs xiaoniao-backend --tail 80`；按下列各行对症 |
| `ModuleNotFoundError: alembic.config` / 依赖异常 | `docker-compose` 挂载 **`./backend:/app`**，宿主机 **`backend/.venv`** 盖住镜像内环境，且为坏/不完整 venv | `docker compose … stop backend celery-worker` → **`sudo rm -rf backend/.venv`** → `docker compose … run --rm --no-deps backend sh -lc 'cd /app && uv sync'` → **`sudo chown -R "$(stat -c %u:%g backend)" backend/.venv`**；或整段用 **`bash infra/deploy/cvm-rebuild-backend.sh`** |
| `Can't find Python file alembic/env.py` | 宿主机 **`backend/alembic/`** 不完整（仅 `versions/` 等） | 从 git 取回 **`env.py` + `script.py.mako`**，或 **rsync 整个 `backend/alembic/`** |
| `password authentication failed for user "xiaoniao"` | **`.env.local` 里密码** 与 **Postgres 数据卷首次初始化时** 不一致；改 env **不会**改已有库口令 | 对齐口令；或接受 **删库重建**：`docker compose … down` → **`docker volume rm <项目>_postgres_data`**（例：`lingniao-golf_postgres_data`）→ 再 `up`（**数据清空**） |
| `curl -I https://…/v1/health` 得 **405** | 用了 **HEAD** | 改用 **GET**：`curl -sk https://…/v1/health` |
| `WARN … xiaoniao-network exists but was not created for project "…"` | 目录名与历史 compose **项目名** 不一致，但 **网络名** 在 compose 里写死为 `xiaoniao-network` | 一般可忽略；若出现 **nginx 无法解析 `backend`**，用 **`docker compose -p xiaoniao …`** 统一项目名或检查是否多套 compose 乱起 |
| `apt update` 报 **`download.docker.com` TLS / handshake** | 官方 Docker 源出网或证书链问题 | `jq` 等可走镜像源仍正常；装 Docker 已完成后可暂忽略，或修源/代理后再 `apt update` |
| `uv` 提示 **hardlink / copy** | 缓存与 `.venv` 跨文件系统 | 可选 `export UV_LINK_MODE=copy` 消除告警，非故障 |
| 预览页白屏 | 没勾「不校验合法域名」 | 设置 → 项目设置 重勾 + 重启工具 |
| `errcode=40029` | wx.login 拿到的 code 拖太久（>5 分钟）才换 | 后端会返回 401 / 业务码 40104，前端会自动重新 wx.login，正常情况无感 |
| `errcode=40013 invalid appid` | `.env.local` 的 `WECHAT_MINIPROGRAM_APPID` 与开发者工具加载的 AppID 不一致 | 改 `.env.local` 后 `make test-restart` |
| 上传视频 504 | nginx `client_max_body_size` 太小（默认 1m） | 已设 `100m`，确认 nginx 起的是 `infra/test/nginx.conf` |
| SSE 卡顿/一坨下发 | nginx 默认开 `proxy_buffering` | 已显式 `off`，且 `chunked_transfer_encoding on` |
| MinIO putObject 跨域 / 403 | `MINIO_PUBLIC_ENDPOINT` 不对 | 应是 `https://$HOST/minio`（不是 `http://localhost:9000`） |
| `make deploy-test` 提示证书未找到 | 未跑 `make test-certs HOST=...`（生成的 **`fullchain.pem`/`privkey.pem`** 缺失） | 先生成证书 |

---

## 七、回滚 / 重置

```bash
# 改了 .env.local，热重启
make test-restart

# 出问题想从头来一遍（⚠️ 会清空 PG/MinIO 数据）
make test-reset
make deploy-test
```

**仅 Postgres 口令与库里不一致**、又接受清空库时，也可：`docker compose … down`，再 **`docker volume rm`** 当前项目在 `docker volume ls` 里的 **`*_postgres_data`** 卷（项目名常等于 compose 目录名，例如 **`lingniao-golf_postgres_data`**），然后 **`make deploy-test`** 或 `docker compose … up -d --build`。

---

## 八、W9 切正式环境的差异（提前打标）

W8 → W9 升级路径，**只需要改这些**：

1. **域名** + **ICP 备案** + **小程序备案** 通过（用户自办）
2. **HTTPS 证书**：Let's Encrypt / 腾讯云 DV；仓库落地步骤见 **`infra/deploy/README.md`**（`make issue-le-cert` / `make renew-le-cert`）；nginx 使用 **`infra/test/certs/fullchain.pem`** / **`privkey.pem`**
3. `.env.local`：
   - `APP_ENV=prod`
   - `QUOTA_MODE=strict`
   - `WECHAT_PAY_MOCK_MODE=false` + 填商户号
4. `client/.env.production`：
   - `TARO_APP_API_BASE_URL=https://api.birdieai.cn/v1`
   - `TARO_APP_PAYMENT_ENABLED=true`
5. 微信开发者工具 → 关闭「不校验合法域名」（必须用合法 HTTPS）

代码层面 W8 → W9 **零改动**，全部走 feature flag。
