# 快速开始（W1 验证清单）

跟着这个文档跑一遍，可以验证 W1 工程骨架是否就绪。

## 前置依赖（一次性）

确保你的 Mac 上已装：

```bash
docker --version          # Docker Desktop
node --version            # 20+
pnpm --version            # pnpm（npm i -g pnpm）
```

如未安装：

```bash
brew install --cask docker     # 装完手动启动 Docker Desktop
brew install node@20
npm install -g pnpm
```

## 步骤 1：初始化环境变量

```bash
cd <仓库根目录>   # 本机克隆路径，例如 ~/Documents/灵鸟golf
make init
```

会复制 `.env.example` → `.env.local`。**默认值即可跑通**，无需改动。

## 步骤 2：启动后端全套服务

```bash
make up
```

这会拉起 5 个容器：
- `xiaoniao-postgres`：数据库
- `xiaoniao-redis`：缓存
- `xiaoniao-minio`：本地对象存储（模拟 COS）
- `xiaoniao-backend`：FastAPI 服务（自动跑 alembic 迁移 + 启动）
- `xiaoniao-ai-engine`：AI 引擎（mock 模式）

第一次运行需要拉镜像 + 装依赖，大约 3-5 分钟。后续启动只需 5-10 秒。

跟踪日志：

```bash
make logs
```

看到类似 `Application startup complete.` 即代表后端就绪。

## 步骤 3：验证后端

```bash
# 1. 健康检查
make check
# 期望返回 {"status": "ok", "services": {"backend": "ok", "database": "ok", "redis": "ok"}}

# 2. 浏览器打开 API 文档
open http://localhost:8000/docs
open http://localhost:9100/docs   # AI 引擎

# 3. MinIO 控制台
open http://localhost:9001
# 账号：minioadmin / minioadmin
# 应该能看到自动创建好的 bucket: xiaoniao-videos
```

## 步骤 4：跑通登录链路（mock 模式）

```bash
# 模拟微信登录（任意 code 都会返回稳定的 mock 用户）
curl -X POST http://localhost:8000/v1/auth/wechat-login \
  -H "Content-Type: application/json" \
  -d '{"code":"hello_world_001"}' | python3 -m json.tool

# 把上面返回的 token 复制下来：
TOKEN="<paste_token_here>"

# 拉取自己信息
curl http://localhost:8000/v1/users/me \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# 完成新用户引导
curl -X POST http://localhost:8000/v1/users/me/onboarding \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"golf_level":"intermediate","primary_goals":["distance","accuracy"],"weekly_practice_frequency":"once"}' \
  | python3 -m json.tool

# 调用 AI 引擎（模拟分析）
curl -X POST http://localhost:9000/analyze \
  -H "Content-Type: application/json" \
  -d '{"analysis_id":"test_001","video_url":"http://demo.mp4","camera_angle":"face_on","club_type":"iron_7"}' \
  | python3 -m json.tool
# 等 2-5 秒返回随机生成的完整挥杆分析报告
```

## 步骤 5：编译微信小程序

```bash
cd client
pnpm install                     # 第一次需要装依赖（约 2-3 分钟）
pnpm build:weapp                 # 或 pnpm dev:weapp（监听模式）
```

正式发布（生产 API、合法域名已就绪）时用 **`make client-build-weapp-prod`**，步骤见 **`docs/release-notes/go-live-weapp-fool-checklist.md`**。

输出在 `client/dist/`（`app.json` 等同目录）。

打开**微信开发者工具**：
1. 导入项目 → 选择 **`client` 目录**（与 `project.config.json` 同级；`miniprogramRoot` 指向 `dist/`）
2. AppID 选"测试号"或填你自己的
3. 应该能看到登录页 → 点"微信一键登录"→ 进入引导流程 → 进入首页

> ⚠️ **注意**：本地开发时小程序需要访问 `localhost:8000`，需要在微信开发者工具的"详情 → 本地设置"里勾选"不校验合法域名"。

### React Native（可选自检）

在仓库根目录执行：

```bash
make client-bootstrap-rn-shell   # 首次：克隆 taro-native-shell 至 client/rn-shell
make client-check-rn              # RN bundle + 日志门禁 + type-check（不启动模拟器）
```

真机与 Pods 详见 [`client/RN_SHELL.md`](client/RN_SHELL.md)。

## 步骤 6（可选）：跑后端测试

```bash
make backend-test
```

## 常见问题

**Q：`make up` 失败，提示端口被占用？**
A：检查 5432/6379/8000/9000/9001 是否被其他服务占用。`lsof -i :8000` 查看后停掉。

**Q：后端日志里看到 `database connect failed`？**
A：第一次启动 PostgreSQL 初始化需要时间，等 30 秒后 `make restart`。

**Q：客户端 `pnpm install` 失败？**
A：网络问题。试试 `pnpm config set registry https://registry.npmmirror.com`。

**Q：在小程序里点登录没反应？**
A：F12 看控制台是否有 401。后端 `WECHAT_MOCK_LOGIN=true` 默认开启，任意 code 都能返回 token。

## 完成 W1 后

下一步是 W2：
- 客户端真实接入微信开发者工具（配置 AppID）
- App 端完整 RN 工程接入（react-native-wechat-lib）
- 真实视频拍摄/上传链路
- 分析任务异步调度（Celery）

我会接着推进。
