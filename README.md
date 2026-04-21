# 小鸟 AI · 高尔夫智能教练

> 中国首款 AI 高尔夫智能教练 —— 双端同步：微信小程序 + iOS/Android App

---

## 项目结构

```
xiaoniao-ai/
├── docs/                     产品/技术文档
├── backend/                  FastAPI 后端服务
├── ai_engine/                AI 视觉分析引擎（独立服务）
├── client/                   Taro 3 客户端（小程序 + RN App 双端共用代码）
├── infra/                    基础设施配置（Dockerfile / k8s）
├── docker-compose.yml        本地一键启动
├── Makefile                  常用命令快捷方式
└── .env.example              环境变量模板
```

---

## 技术栈

| 层 | 技术 |
|----|------|
| 客户端 | Taro 3 + React 18 + TypeScript（同时编译 微信小程序 + React Native） |
| 后端 | Python 3.11 + FastAPI + SQLAlchemy 2 + Pydantic v2 + Celery |
| 数据库 | PostgreSQL 16 + Redis 7 |
| 对象存储 | 本地 MinIO / 生产 腾讯云 COS |
| AI 引擎 | MediaPipe + OpenCV + PyTorch |
| LLM | DeepSeek（默认，可切换至 Qwen / GLM / OpenAI） |
| 部署 | Docker + Docker Compose（生产 K8s） |

---

## 快速开始

### 1. 前置依赖

请先在你的 Mac 上安装：

```bash
# Docker Desktop（必须）
brew install --cask docker

# Node.js 18+ 与 pnpm（客户端开发用）
brew install node@20
npm install -g pnpm

# Python 3.11 + uv（如需在容器外开发后端）
brew install python@3.11
curl -LsSf https://astral.sh/uv/install.sh | sh

# 微信开发者工具（小程序调试）
# 下载：https://developers.weixin.qq.com/miniprogram/dev/devtools/download.html
```

### 2. 初始化环境变量

```bash
make init
# 等价于 cp .env.example .env.local
```

然后编辑 `.env.local`，按需填入真实的密钥。**首次跑通无需修改**，所有占位值都能让本地 mock 模式工作。

### 3. 一键启动后端全套服务

```bash
make up
```

启动后访问：
- **后端 API 文档**：<http://localhost:8000/docs>
- **AI 引擎 API 文档**：<http://localhost:9100/docs>
- **MinIO 控制台**：<http://localhost:9001>（账号 `minioadmin` / `minioadmin`）

健康检查：

```bash
make check
# 应返回 {"status": "ok", ...}
```

### 4. 启动客户端（微信小程序）

```bash
make client-install              # 首次运行
make client-dev-weapp            # 编译到 client/dist/weapp
```

打开**微信开发者工具** → 导入项目 → 选择 `client/dist/weapp` 目录。

### 5. 启动客户端（React Native App）

```bash
# iOS（需要 Mac + Xcode）
make client-dev-rn-ios

# Android（需要 Android Studio + 模拟器）
make client-dev-rn-android
```

---

## 开发流程

### 后端

- 修改 `backend/app/` 下的代码会**热重载**
- 数据库模型变更后：`make backend-revision m="add foo column"` → `make backend-migrate`
- 进入容器调试：`make backend-shell`

### 客户端

- 共享代码在 `client/src/`
- 端差异化使用 `process.env.TARO_ENV` 判断（值为 `weapp` / `rn`）
- 业务逻辑、API 调用、Store 在双端完全共享

---

## 常用命令

```bash
make help               # 查看全部命令
make logs               # 查看实时日志
make ps                 # 查看服务状态
make down               # 停止服务（保留数据）
make reset              # 彻底重置（清理数据）

# 质量门（W6-T5）
make test               # backend + ai_engine + client tsc 全量单测 + lint
make ci                 # test 基础上 + 真实引擎 smoke（bouncing_box → 50103）
```

### 资源占用参考（W6-T5 实测）

| 服务 | 镜像大小 | 峰值内存 | 并发 |
|---|---|---|---|
| `ai_engine` | ~2.5 GB（含 mediapipe + opencv + ffmpeg） | ~800 MB（单视频推理） | uvicorn 1 worker → 同一时刻 1 条 |
| `celery-worker` | 共享 backend 镜像 | ~300 MB | `--concurrency=2` → 同一时刻 2 条派发到 ai_engine |
| `backend` | ~450 MB | ~200 MB | uvicorn 1 worker（`--reload`） |

生产扩容：ai_engine 单机 ≥ 4 GB；双 worker 要 **另起一个 ai_engine 容器**（uvicorn 不要 `--workers 2`，mediapipe 模型加载成本高且非线程安全）。

---

## 文档

完整设计文档见 [`docs/`](./docs)：

| 文档 | 内容 |
|------|------|
| [产品白皮书](./小鸟AI高尔夫-产品设计白皮书.md) | 市场、定位、商业模式；**§7.2 全端视觉规范（深绿+白+金，权威）** |
| [01-MVP 功能需求](./docs/01-MVP功能需求规格说明书.md) | 功能规格 + 验收标准 |
| [02-API 设计](./docs/02-API接口设计文档.md) | 39 个接口详细定义 |
| [03-数据库设计](./docs/03-数据库设计文档.md) | 表结构 + 索引 |
| [04-工程规范](./docs/04-项目工程规范文档.md) | 代码规范 + Git 流程 |
| [05-AI 模型规格](./docs/05-AI模型技术规格文档.md) | AI Pipeline 设计 |
| [06-数据安全合规](./docs/06-数据安全与隐私合规文档.md) | PIPL 合规 |
| [07-测试策略](./docs/07-测试策略文档.md) | 单元/集成/E2E |
| [08-知识库建设](./docs/08-高尔夫知识库建设方案.md) | RAG 知识库 |
| [09-运营支撑](./docs/09-运营支撑文档.md) | 后台管理 + 数据分析 |
| [10-Git 协作规范](./docs/10-Git协作规范.md) | 分支 / Conventional Commits / PR 流程 |
| [11-M1 任务拆分](./docs/11-M1任务拆分.md) | 用户体系的 5 个可独立合入子任务 |
| [12-M2 任务拆分](./docs/12-M2任务拆分.md) | 核心分析链路（W3-W4）的 6 个子任务 |
| [13-M3 任务拆分](./docs/13-M3任务拆分.md) | AI 对话教练（W5）的 6 个子任务 |
| [14-W6 任务拆分](./docs/14-W6任务拆分.md) | AI 真实引擎替换（W6）的 6 个子任务 |
| [API 联调示例](./docs/api-examples/) | M1 端到端 curl 脚本（登录→引导→编辑→刷新） |
| [AGENTS.md](./AGENTS.md) | AI 协同工作约定（Cursor 等会话首读） |

---

## 当前进度

- [x] **W1**：Monorepo 工程基建
- [x] **W2**：用户体系（双端登录打通、3 步引导、"我的"最小版；详见 [M1 任务拆分](./docs/11-M1任务拆分.md)）
- [x] **W3-W4**：核心分析链路（上传 → Celery + Mock 分析 → 报告页 + 历史 + 示例视频体验；详见 [M2 任务拆分](./docs/12-M2任务拆分.md) 与 [W3-W4 走查记录](./docs/release-notes/W3-W4-walkthrough.md)）
- [x] W5：AI 对话（LLM 流式接入）—— M3-T1 后端骨架/配额 ✅ · M3-T2 LLM 客户端 + system prompt + SSE 流式 ✅ · M3-T3 前端对话页 + 非流式打通 ✅ · M3-T4 前端 SSE 流式 + 打字动画 + drill_card ✅ · M3-T5 报告页/首页入口闭环 ✅ · M3-T6 文档同步 + walkthrough ✅
- [ ] W6：AI 真实引擎替换
- [ ] W7：商业化与社交（支付 + 邀请 + 训练）
- [ ] W8：双端发布准备

---

## 许可

内部机密 · © 2026 小鸟 AI
