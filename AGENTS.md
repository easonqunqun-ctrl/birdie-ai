# AGENTS.md — AI 协同工作约定

> 本文件是 **Cursor、其他 AI 编码助手** 在本仓库工作时的唯一规范入口。
> 每次新会话若未加载上下文，优先读本文件；与其他文档冲突时，**本文件优先**。

---

## 0. 产品一句话

**领翼golf** 是面向中国球友的 **AI 高尔夫私教**：拍一段挥杆视频 → AI 出报告 → 给训练建议 → AI 对话答疑 → 打卡闭环。载体以微信小程序为主，App（RN）为辅。

---

## 1. 仓库结构（只改该改的）

```
backend/       FastAPI + PostgreSQL + Redis（业务后端）
ai_engine/     独立 AI 视觉分析服务（mock 模式默认开启）
client/        Taro 3 + React 18 + TS（编译 微信小程序 / React Native）
docs/          产品、API、数据库、规范、测试、知识库、运营文档
UI/            UI 原型 HTML 与生成图（仅参考，勿当源码）
小鸟AI高尔夫-产品设计白皮书.md   产品与视觉规范权威文档
```

**改动边界**：
- 涉及产品/视觉/接口契约的变更，**必须先改对应 `docs/*` 与白皮书**，再改代码。
- `UI/` 目录是设计原型，**不要**把它当作前端真源码去改。
- 未被点名的大范围重构、依赖替换、目录搬迁：**禁止**。

---

## 2. 技术栈与版本（开工前默认值）

| 层 | 技术 |
|----|------|
| 客户端 | Taro 3.6.x + React 18 + TypeScript 5 + Zustand 4（**pnpm**） |
| 后端 | Python 3.11 + FastAPI + SQLAlchemy 2（async） + Alembic + Pydantic v2（**uv**） |
| AI 引擎 | FastAPI + MediaPipe + OpenCV（MVP 期默认 mock 模式） |
| 数据库 / 缓存 / 存储 | PostgreSQL 16 / Redis 7 / MinIO（本地）→ 腾讯云 COS（生产） |
| LLM | DeepSeek 默认，可切 Qwen / GLM / OpenAI |
| 编排 | Docker Compose（本地）→ 腾讯云 TKE（生产） |

**包管理**：客户端 **必须用 pnpm**，后端/AI **必须用 uv**。**不要**擅自切换到 npm / yarn / pip。

---

## 3. 视觉规范（硬性约束）

**三色体系：深绿 + 白 + 金**（详见《产品设计白皮书》§7.2）。

- 深绿定调、白承载信息、金小面积点缀（会员/成就/关键数据）。
- **严禁**：荧光绿、浅薄荷绿、Tailwind 默认 emerald 作为主品牌色。
- **严禁**：在业务页面 SCSS / TSX 里硬编码品牌相关 HEX；**一律走 `client/src/app.scss` 里的 CSS 变量**（如 `var(--color-primary)`、`var(--color-gold)`）。
- 语义色（success / warning / error）仅用于状态提示与图表，不覆盖品牌主色。

---

## 4. 客户端跨端守则

- 平台差异 API（登录、拍摄、上传、震动等）**只在** `src/adapters/*` 里分叉，**不要**在页面组件里写 `if (process.env.TARO_ENV === 'weapp')`。
- 样式 **以 flex 为主**；避免 grid / float / 复杂选择器（RN 不支持）。
- 路由跳转统一用 `Taro.navigateTo` / `Taro.reLaunch`；不要直接拼 URL。
- 新建页面：同时建 `.tsx` / `.scss` / `.config.ts` 三件套，并在 `app.config.ts` 中登记。

---

## 5. 后端与数据库守则

- **不要**直接手改数据库结构：改 `app/models/*.py` → `make backend-revision m="..."` → `make backend-migrate`。
- 新接口必须同步更新 [`docs/02-API接口设计文档.md`](docs/02-API接口设计文档.md)；字段名、错误码、分页约定以该文档为准。
- Pydantic Schema 放 `app/schemas/`，ORM 模型放 `app/models/`，业务逻辑放 `app/services/`，路由仅做参数校验和调度。
- 所有面向 C 端的接口默认挂 JWT 鉴权；mock 登录由 `WECHAT_MOCK_LOGIN=true` 控制，不要在代码里写死。

---

## 6. Git / 提交 / PR

详见 [`docs/10-Git协作规范.md`](docs/10-Git协作规范.md)。速记：

- 分支：`feat/<模块>-<简述>`、`fix/<简述>`、`chore/<简述>`、`docs/<简述>`。
- Commit：**Conventional Commits**（`feat:`、`fix:`、`docs:`、`chore:`、`refactor:`、`test:`、`style:` 七类）。
- PR：**一件事一 PR**，模板强制填 "变更点 / 影响范围 / 自测记录 / 文档同步"。
- **未经要求不得**：强推、改 git 配置、改动别人正在进行的分支、合并到 main/master。

---

## 7. 命令速查（对 AI 也一样）

```bash
# 本地一键起全套
make init && make up && make check

# 客户端
cd client && pnpm install && pnpm dev:weapp
cd client && pnpm type-check && pnpm lint
make client-bootstrap-rn-shell       # RN：首次克隆 taro-native-shell 至 client/rn-shell（幂等）
make client-check-rn                  # RN：bundle 门禁 + type-check（已并入 make test；CI：.github/workflows/client-rn-check.yml）
make client-build-weapp-prod          # 微信小程序正式包：先填 client/.env.production，见 docs/release-notes/go-live-weapp-fool-checklist.md

# CVM / HTTPS（微信小程序真机须可信 CA；详见 infra/deploy/README.md）
make deploy-check-env                              # 自检 .env.local 占位符等（ENV_FILE= 可改路径）
bash infra/deploy/cvm-rebuild-backend.sh         # CVM：backend 绑定挂载 + .venv / uv sync / 重建
make issue-le-cert EMAIL=you@example.com DOMAIN=api.example.com
make renew-le-cert DOMAIN=api.example.com
make sync-le-certs DOMAIN=api.example.com
make publish-backend-cvm                 # CVM：无 Git 时用 scp+ssh（默认 ubuntu@1.13.198.172；须在本地 Terminal 交互输 SSH 密码，见 infra/deploy/publish-backend-to-cvm.sh）
# W8 从零搭机：docs/release-notes/W8-test-env-runbook.md；**规范化/Git+密钥+去 bind**：docs/release-notes/CVM-canonical-deploy.md

# 后端
make backend-lint     # ruff
make backend-test     # pytest
make backend-revision m="add xxx column"
make backend-migrate
```

---

## 8. 明确的"不要做"清单

- 不要在未读 `docs/01-MVP功能需求规格说明书.md` 对应模块前，凭想象写业务代码。
- 不要把占位页（`coach/` `training/`）"顺手"补齐，这些按 W5 / W7 排期，会冲突。
- 不要引入新的 UI 库（NutUI / TDesign 等）除非经过产品与工程双方确认，当前只用 `@tarojs/components` + 自研样式。
- 不要把 `.env.local`、`*.p8`、`*.key`、`*.mobileprovision` 等敏感文件加入提交。
- 不要把 `UI/*.png`（几 MB 的图）二次复制到代码目录，引用时保持在 `UI/`。

---

## 9. 当需要澄清时

- 产品意图不明 → 翻 `小鸟AI高尔夫-产品设计白皮书.md`（§5 功能规划 / §7 信息架构 / §7.2 视觉规范）。
- 接口字段不明 → `docs/02-API接口设计文档.md`。
- 数据库字段不明 → `docs/03-数据库设计文档.md`。
- 仍不明 → **停下来问用户**，不要臆测实现。
