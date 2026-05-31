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
灵鸟golf-产品设计白皮书.md   产品与视觉规范权威文档
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

**四色体系：靛蓝 + 白 + 金 + 点缀绿**（详见《产品设计白皮书》§7.2，**以 `client/src/app.scss` CSS 变量为权威源**）。

- 主色 `--color-primary: #1a237e`（冷靛蓝）定调；白承载信息；金 `--color-gold: #c9a227` 小面积点缀（会员/成就/关键数据）；点缀绿 `--color-accent-mint: #00d084` 仅用于「成长 / 完成 / 上行」语义。
- **严禁**：荧光绿、浅薄荷绿、Tailwind 默认 emerald、Material 深绿等作为主品牌色；金色不得用作主 CTA 填充。
- **严禁**：在业务页面 SCSS / TSX 里硬编码品牌相关 HEX；**一律走 `client/src/app.scss` 里的 CSS 变量**（`var(--color-primary)` / `var(--color-gold)` / `var(--gradient-hero)` 等）。
- **TabBar / SVG / `app.config.ts`** 等不支持 CSS 变量的场合可硬编码，但 HEX 必须与白皮书 §7.2.1 表完全一致。
- 语义色（success / warning / error / amber / info）仅用于状态提示与图表，不覆盖品牌主色。

---

## 4. 客户端跨端守则

- 平台差异 API（登录、拍摄、上传、震动等）**只在** `src/adapters/*` 里分叉，**不要**在页面组件里写 `if (process.env.TARO_ENV === 'weapp')`。
- 样式 **以 flex 为主**；避免 grid / float / 复杂选择器（RN 不支持）。
- 路由跳转统一用 `Taro.navigateTo` / `Taro.reLaunch`；不要直接拼 URL。
- 新建页面：同时建 `.tsx` / `.scss` / `.config.ts` 三件套，并在 `app.config.ts` 中登记。
- **前端单测**（W9 起强制门禁，详见 [`docs/07`](docs/07-测试策略文档.md) §2.1）：
  - 修改 `src/services` / `src/utils` / `src/store` / `src/components/*.tsx`（非 `.rn.tsx`）**必须同步加 / 更新**对应 `__tests__/*.test.ts`。
  - 新增 Taro API 调用前，**先**到 `src/__mocks__/tarojs.ts` 里补 `jest.fn` 桩，再写测试，避免每个测试文件手工 mock 同一 API。
  - 不要在测试里直接 import 真实 `@tarojs/taro` / `@tarojs/components`：jsdom 下会触发小程序运行时初始化失败。
  - 端分叉 `*.rn.tsx` / `adapters/*.{weapp,rn}.ts` 不纳入 Jest，由 `make client-check-rn` + 真机 smoke 兜底。

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
make client-test                      # Jest 单测（services/utils/store/components 端无关层；首次需先 pnpm install）
make client-test-coverage             # 带覆盖率阈值；CI 走 client-test-ci，见 .github/workflows/client-jest.yml；详 docs/07
make client-build-weapp-prod          # 微信小程序正式包：先填 client/.env.production，见 docs/release-notes/go-live-weapp-fool-checklist.md

# CVM / HTTPS（微信小程序真机须可信 CA；详见 infra/deploy/README.md）
make deploy-check-env                              # 自检 .env.local 占位符等（ENV_FILE= 可改路径）
bash infra/deploy/cvm-rebuild-backend.sh         # CVM：backend 绑定挂载 + .venv / uv sync / 重建
make issue-le-cert EMAIL=you@example.com DOMAIN=api.example.com
make renew-le-cert DOMAIN=api.example.com
make sync-le-certs DOMAIN=api.example.com
make setup-cvm-ssh-key                 # 路径 B：一次 ssh-copy-id 后免密发布
make publish-backend-cvm               # CVM：scp+compose（优先 ~/.ssh/id_ed25519_birdie_golf）；远端会先跑支付挂载自检
make publish-monitoring-cvm            # CVM：rsync infra/monitoring + 重启 prometheus/alertmanager/bridge
make deploy-check-cvm-pay               # WECHAT_PAY_MOCK_MODE=false 时须有 docker-compose.wechat-pay-key.yml（ENV_FILE= 可改）
# W8 从零搭机：docs/release-notes/W8-test-env-runbook.md；**规范化/Git+密钥+去 bind**：docs/release-notes/CVM-canonical-deploy.md；**顺滑发版/踩坑**：docs/release-notes/cvm-release-smooth-runbook.md

# 体验版发版（用户说「发版/发布」时由 AI 执行，勿只贴命令）
# DEPLOY_HOST=ubuntu@1.13.198.172 ENV_FILE=~/secrets/lingniao-prod.env make cvm-preflight
# git push origin main && make ship-cvm   # 或已 push：make release-cvm
# make client-build-weapp-prod && 更新 docs/release-notes/experience-version-smoke-runbook.md
# 细则：.cursor/rules/cvm-release.mdc · docs/release-notes/cvm-release-smooth-runbook.md

# 后端
make backend-lint     # ruff
make backend-test     # pytest
make backend-revision m="add xxx column"
make backend-migrate
# 分析报告软删除：上线档位 R0/R1、Smoke、与支付交叉约定 → docs/release-notes/analysis-soft-delete-release-pattern.md
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

- 产品意图不明 → 翻 `灵鸟golf-产品设计白皮书.md`（§5 功能规划 / §7 信息架构 / §7.2 视觉规范）。
- **MVP 一期收尾（真引擎可观测、明确不做项）** → [`docs/19-产品开发迭代计划-当前队列.md`](docs/19-产品开发迭代计划-当前队列.md) **§七**（**详单**：§六、`docs/01`）。
- **AI 引擎产品力**（评分哲学与话术、ECS 标定集、Trust/Calibration/Consensus 三线）→ [`docs/20-AI引擎产品力迭代设计.md`](docs/20-AI引擎产品力迭代设计.md)（白皮书 **§5.2.1**）；**站会 PLAN-ID** → [`docs/19` §6.3 **ENG-***](docs/19-产品开发迭代计划-当前队列.md#63-主表plan-id)；**验收** → [`docs/01` §4.5](docs/01-MVP功能需求规格说明书.md#45-ai-引擎产品力对齐-docs20)。
- 接口字段不明 → `docs/02-API接口设计文档.md`。
- 数据库字段不明 → `docs/03-数据库设计文档.md`。
- **分析报告软删除**何时算「可发版」、发布顺序与 R2 backlog → [`docs/release-notes/analysis-soft-delete-release-pattern.md`](docs/release-notes/analysis-soft-delete-release-pattern.md)。
- **体验版一轮测试**（自动化 + 微信侧 Smoke）→ [`docs/release-notes/experience-version-smoke-runbook.md`](docs/release-notes/experience-version-smoke-runbook.md)。
- 仍不明 → **停下来问用户**，不要臆测实现。
