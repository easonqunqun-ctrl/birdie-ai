.PHONY: help init up down compose-reconcile restart logs ps clean reset \
        backend-shell backend-logs backend-test backend-test-smoke backend-lint backend-migrate backend-revision \
        backend-celery-logs backend-celery-shell \
        ai-shell ai-logs ai-engine-test ai-engine-test-local ai-engine-lint ai-engine-smoke \
        ai-engine-ecs-regression ai-engine-synth-fixtures \
        client-install client-bootstrap-rn-shell client-dev-weapp client-dev-rn-ios client-dev-rn-android \
        client-build-weapp client-build-weapp-prod client-build-rn client-tsc client-check-rn \
        client-test client-test-watch client-test-coverage client-test-ci \
        check test ci \
        deploy-check-env deploy-check-cvm-pay \
        deploy-test test-logs test-ps test-reset test-restart test-certs test-health \
        issue-le-cert sync-le-certs renew-le-cert verify-weapp-https \
        deploy-cvm-up deploy-cvm-ps deploy-cvm-logs publish-backend-cvm publish-monitoring-cvm setup-cvm-ssh-key \
        release-cvm ship-cvm cvm-migrate-git-doc cvm-stable-from-mac cvm-deploy-help cvm-deploy-dry-run cvm-env-preflight cvm-preflight cvm-preflight-tls cvm-remote-release cvm-smoke

# 默认目标：显示帮助
help:
	@echo "「小鸟 AI」开发命令清单"
	@echo ""
	@echo "  ===== 一键操作 ====="
	@echo "  make init              首次初始化（复制 .env、安装依赖）"
	@echo "  make up                启动全部服务（PostgreSQL+Redis+MinIO+Backend+AI）"
	@echo "  make down              停止全部服务"
	@echo "  make compose-reconcile 若 up 报网络/container 冲突：收口旧 compose 栈后再 up"
	@echo "  make restart           重启全部服务"
	@echo "  make logs              查看实时日志"
	@echo "  make ps                查看服务状态"
	@echo "  make clean             清理容器（保留数据）"
	@echo "  make reset             清理容器和数据卷（彻底重置）"
	@echo ""
	@echo "  ===== 后端 ====="
	@echo "  make backend-shell     进入后端容器"
	@echo "  make backend-logs      查看后端日志"
	@echo "  make backend-test      运行后端测试（全套 pytest）"
	@echo "  make backend-test-smoke  CI 对齐冒烟子集（需先 make up）"
	@echo "  make backend-lint      代码检查（ruff）"
	@echo "  make backend-migrate   执行数据库迁移"
	@echo "  make backend-revision m='msg'  生成新的迁移脚本"
	@echo "  make backend-celery-logs  查看 Celery worker 日志"
	@echo "  make backend-celery-shell 进入 Celery worker 容器"
	@echo ""
	@echo "  ===== AI 引擎 ====="
	@echo "  make ai-shell                 进入 AI Engine 容器"
	@echo "  make ai-logs                  查看 AI Engine 日志"
	@echo "  make ai-engine-test           在容器里运行 AI Engine 测试"
	@echo "  make ai-engine-test-local     在宿主机 ai_engine/ 目录下 uv run pytest"
	@echo "  make ai-engine-lint           ruff check ai_engine/app"
	@echo "  make ai-engine-synth-fixtures 生成合成测试视频（需要本机装 ffmpeg）"
	@echo "  make ai-engine-ecs-regression   ENG-04 ECS v1 CI 回归单测（宿主机 uv）"
	@echo ""
	@echo "  ===== 客户端（Taro 双端） ====="
	@echo "  make client-install         安装客户端依赖"
	@echo "  make client-test            Jest 单测（默认本地交互）"
	@echo "  make client-test-watch      Jest 监听模式"
	@echo "  make client-test-coverage   Jest 覆盖率（带阈值检查）"
	@echo "  make client-test-ci         Jest CI 模式（单 worker + silent）"
	@echo "  make client-bootstrap-rn-shell 克隆 taro-native-shell 到 client/rn-shell（幂等）"
	@echo "  make client-dev-weapp       开发：编译微信小程序（用 微信开发者工具 打开 client/dist）"
	@echo "  make client-dev-rn-ios      开发：iOS App"
	@echo "  make client-dev-rn-android  开发：Android App"
	@echo "  make client-build-weapp     微信小程序构建（默认 dev 变量）"
	@echo "  make client-build-weapp-prod  正式小程序包（校验 .env.production 后 production 构建）"
	@echo "  make client-build-rn        RN：taro build + 日志门禁（reject error src / Unable）"
	@echo "  make client-check-rn        RN bundle 门禁 + client type-check（已并入 make test）"
	@echo ""
	@echo "  ===== 健康检查 ====="
	@echo "  make check             检查后端 /v1/health"
	@echo ""
	@echo "  ===== 质量门（T5） ====="
	@echo "  make test              rollup：后端 + AI 引擎 + 客户端（RN bundle + tsc）"
	@echo "  make ci                test + 真实引擎 smoke（bouncing_box → 50103）"
	@echo ""
	@echo "  ===== W8-T4：云发版（最简单）======"
	@echo "  make setup-cvm-ssh-key     仅一次：专用密钥 + ssh-copy-id（输最后一次服务器密码），之后 make release-cvm 免密"
	@echo "  make ship-cvm              本机：生产 env 预检 → git push main → SSH 远端发版（须 main + 已 setup-cvm-ssh-key）"
	@echo "  make release-cvm           代码已在 Git 远端后：SSH 整包 compose + alembic（可选 CVM_LOCAL_PREFLIGHT=1 ENV_FILE=…）"
	@echo "  顺滑发版说明     docs/release-notes/cvm-release-smooth-runbook.md"
	@echo "  make cvm-migrate-git-doc   云上从 rsync 切 git clone：读 docs/release-notes/CVM-migrate-rsync-to-git.md"
	@echo "  make publish-backend-cvm   无云上 git：scp compose 三件套 + rsync backend/ai_engine → 远端 build + alembic"
	@echo "                              （REMOTE_RSYNC_COMPOSE=no 可跳过 scp compose；慎用）"
	@echo "  make publish-monitoring-cvm  rsync infra/monitoring + 重启 monitoring profile（PushPlus/告警 rule）"
	@echo "  ===== W8-T4：测试环境与证书（按需）======"
	@echo "  make deploy-check-env     自检 .env.local 尖括号/穿透占位（可加 ENV_FILE=路径）"
	@echo "  make deploy-check-cvm-pay WECHAT_PAY_MOCK=false 时须有 docker-compose.wechat-pay-key.yml（ENV_FILE=）"
	@echo "  bash infra/deploy/cvm-rebuild-backend.sh   CVM：backend 绑定挂载 + .venv/uv sync + 重建（见文档）"
	@echo "  make test-certs HOST=...  生成自签 HTTPS 证书（首次部署前）"
	@echo "  make deploy-test          一键起测试栈（compose -f base -f test）"
	@echo "  make deploy-cvm-up        CVM：+ docker-compose.cvm.yml；若存在 docker-compose.wechat-pay-key.yml 则自动挂商户 PEM；发版前自动跑 deploy-check-cvm-pay"
	@echo "  make cvm-deploy-help      CVM：打印 deploy-cvm.sh 阶段说明"
	@echo "  make cvm-deploy-dry-run   CVM：打印服务端建议 compose / curl 片段（不执行 SSH）"
	@echo "  make cvm-preflight        推荐：先发版前跑一次（占位符自检 + 真实支付 compose 挂载）"
	@echo "  make cvm-env-preflight    等价调用 deploy-cvm.sh --local-preflight（内含上两项）"
	@echo "  make cvm-preflight-tls    cvm-preflight 再跑 verify-weapp-https DOMAIN=默认 api.b…"
	@echo "  make cvm-stable-from-mac  稳妥：ENV_FILE=真实文件路径.env（勿用文档占位符字面量）→ 预检→TLS→release；DRY_RUN=1 只预检"
	@echo "  make cvm-remote-release   DEPLOY_HOST=… 上 SSH 远端执行 release…（可加 CVM_LOCAL_PREFLIGHT=1 ENV_FILE=…）"
	@echo "  make cvm-smoke DOMAIN=api… TOKEN=可选  HTTPS 冒烟（curl /v1/health + 可选 Bearer）"
	@echo "  make setup-cvm-ssh-key     路径 B：专用 ed25519 + ssh-copy-id（只一次输服务器密码）"
	@echo "  make test-logs            tail 测试栈所有服务日志"
	@echo "  make test-ps              查看测试栈状态"
	@echo "  make test-restart         重启测试栈"
	@echo "  make test-health          curl https 自签证书走一遍 /v1/health"
	@echo "  make issue-le-cert EMAIL=you@domain DOMAIN=api.birdieai.cn   Let's Encrypt（栈须已起）"
	@echo "  make renew-le-cert DOMAIN=api.birdieai.cn                   Let's Encrypt 续约（Docker certbot）"
	@echo "  make sync-le-certs DOMAIN=api.birdieai.cn                    同步 LE 证书进 infra/test/certs 并重载 nginx"
	@echo "  make verify-weapp-https DOMAIN=api.birdieai.cn               外网 TLS + /v1/health + ACME 路径自检（不需登录微信后台）"
	@echo "  make test-reset           ⚠️ 销毁全部容器+卷（含 PG/Minio 数据）"

# ==================== 一键操作 ====================
init:
	@if [ ! -f .env.local ]; then \
		cp .env.example .env.local; \
		echo "✓ .env.local 已创建，请编辑填入真实配置"; \
	else \
		echo "✓ .env.local 已存在"; \
	fi
	@echo "提示：首次启动前请执行 make up"

up:
	docker compose --env-file .env.local up -d --build
	@echo ""
	@echo "✓ 服务已启动："
	@echo "  • Backend API:    http://localhost:8000/docs"
	@echo "  • AI Engine:      http://localhost:9100/docs"
	@echo "  • MinIO Console:  http://localhost:9001 (minioadmin/minioadmin)"
	@echo "  • PostgreSQL:     localhost:5432"
	@echo "  • Redis:          localhost:6379"

down:
	docker compose --env-file .env.local down

compose-reconcile:
	@echo "→ 收口遗留 Compose（常见：另一目录克隆推导为 project=ai / golf）…"
	-docker compose -p ai --env-file .env.local -f docker-compose.yml down --remove-orphans
	-docker compose -p golf --env-file .env.local -f docker-compose.yml down --remove-orphans
	@echo "→ 按 Docker 标签强制删除仍挂名 project=ai 的容器（释放固定 container_name）…"
	@if docker ps -aq --filter label=com.docker.compose.project=ai | grep -q .; then \
		docker ps -aq --filter label=com.docker.compose.project=ai | xargs docker rm -f || true; \
	else \
		echo "(无 project=ai 容器)"; fi
	@echo "→ 收口本项目（Compose 顶层 name:xiaoniao）栈…"
	-docker compose --env-file .env.local down --remove-orphans
	@echo ""
	@echo "✓ reconcile 完成；再执行 make up"

restart: down up

logs:
	docker compose --env-file .env.local logs -f --tail=100

ps:
	docker compose --env-file .env.local ps

clean:
	docker compose --env-file .env.local down --remove-orphans

reset:
	docker compose --env-file .env.local down -v --remove-orphans
	@echo "✓ 已清理所有容器和数据"

# ==================== 后端 ====================
# 仅跑与 `backend-pytest-smoke.yml` 一致的子集（需先 `make up`）。
backend-test-smoke:
	docker compose --env-file .env.local exec backend uv run pytest \
	  tests/test_parallel_backlog_regressions.py tests/test_health.py tests/test_quota_unlimited.py \
	  tests/test_training.py::test_add_to_plan_from_analysis_creates_plan \
	  tests/test_training.py::test_add_to_plan_from_analysis_rejects_sample \
	  tests/test_payments.py::test_expire_stale_pending_orders_closes_old_pending \
	  tests/test_storage_presign_contract.py \
	  -q --tb=short

backend-shell:
	docker compose --env-file .env.local exec backend sh

backend-logs:
	docker compose --env-file .env.local logs -f --tail=200 backend

backend-test:
	docker compose --env-file .env.local exec backend uv run pytest -v

backend-lint:
	docker compose --env-file .env.local exec backend uv run ruff check app/

backend-migrate:
	docker compose --env-file .env.local exec backend uv run alembic upgrade head

backend-revision:
	@if [ -z "$(m)" ]; then \
		echo "用法: make backend-revision m='your migration message'"; \
		exit 1; \
	fi
	docker compose --env-file .env.local exec backend uv run alembic revision --autogenerate -m "$(m)"

backend-celery-logs:
	docker compose --env-file .env.local logs -f --tail=200 celery-worker

backend-celery-shell:
	docker compose --env-file .env.local exec celery-worker sh

# ==================== AI 引擎 ====================
ai-shell:
	docker compose --env-file .env.local exec ai_engine sh

ai-logs:
	docker compose --env-file .env.local logs -f --tail=200 ai_engine

# 在容器内跑（要求 make up 已起 ai_engine，且镜像已 build 并装了 mediapipe + ffmpeg）
# 跑 pytest 前自动生成合成测试视频（T1 质量门失败分支需要）；已有则覆盖，总耗时 < 2s。
# real/*.mp4 是版权受限的真实挥杆视频，不会自动生成，缺失时对应测试会自动 skip。
ai-engine-test:
	@docker compose --env-file .env.local exec ai_engine bash -c "\
		bash tests/fixtures/generate_synthetic.sh && \
		uv run pytest -v"

# 在宿主机跑（用 uv 在 ai_engine/.venv 里跑；没装 mediapipe/ffmpeg 的测试会自动 skip）
ai-engine-test-local:
	cd ai_engine && uv run pytest -v

# W6-T5：优先跑容器内（不要求宿主机装 uv）；容器没起时 fallback 到宿主机 uv
ai-engine-lint:
	@if docker compose --env-file .env.local ps ai_engine --format json 2>/dev/null | grep -q '"State":"running"'; then \
		docker compose --env-file .env.local exec -T ai_engine uv run ruff check app/ tests/; \
	else \
		cd ai_engine && uv run ruff check app/ tests/; \
	fi

ai-engine-synth-fixtures:
	@bash ai_engine/tests/fixtures/generate_synthetic.sh

ai-engine-ecs-regression:
	cd ai_engine && uv run pytest tests/test_ecs_regression.py -v --tb=short

# W6-T5：真实引擎 smoke（直接 curl /analyze 跑 bouncing_box，验证不崩 + 错误码正确）。
# 用于 CI 保护：任何让 pipeline 彻底跑不起来的改动都会在这里露馅。
ai-engine-smoke:
	@echo "=> bouncing_box 应返回 50103（未检测到人物）"
	@docker compose --env-file .env.local exec -T ai_engine bash -c '\
		curl -sf http://localhost:9000/health > /dev/null && \
		echo "health ok" && \
		curl -s -X POST http://localhost:9000/analyze \
			-H "content-type: application/json" \
			-d "{\"analysis_id\":\"smoke\",\"user_id\":\"u\",\"video_url\":\"/app/tests/fixtures/synthetic/bouncing_box.mp4\",\"duration_ms\":3000,\"membership_status\":\"free\",\"camera_angle\":\"face_on\",\"club_type\":\"iron_7\"}" \
			| python3 -c "import json,sys; d=json.load(sys.stdin); assert d[\"status\"]==\"failed\" and d[\"error_code\"]==50103, d; print(\"smoke ok:\", d[\"error_code\"], d[\"error_message\"])"'

# ==================== 客户端 ====================
client-install:
	cd client && pnpm install

client-bootstrap-rn-shell:
	cd client && bash scripts/bootstrap-rn-shell.sh

client-dev-weapp:
	cd client && pnpm dev:weapp

client-dev-rn-ios:
	cd client && pnpm dev:rn:ios

client-dev-rn-android:
	cd client && pnpm dev:rn:android

client-build-weapp:
	cd client && pnpm build:weapp

# 正式上线：校验 https API 占位 → dist/（详见 docs/release-notes/go-live-weapp-fool-checklist.md）
client-build-weapp-prod:
	cd client && pnpm build:weapp:prod:check

# RN：Metro/taro-css 报错时 CLI 偶尔仍 exit 0，故对 rn-build.log 做强校验。
client-build-rn:
	cd client && bash -c '\
		set -o pipefail; \
		pnpm build:rn 2>&1 | tee rn-build.log; \
		ev=$$?; \
		if grep -Eq "^error src/|^error Unable" rn-build.log 2>/dev/null; then \
			echo ""; echo "✗ RN 构建日志含硬错误（见 client/rn-build.log）"; exit 1; \
		fi; \
		exit $$ev'

# W6-T5：客户端 TS 类型检查（不出 bundle，单纯类型门）
client-tsc:
	cd client && pnpm type-check

# RN bundle + 类型（已并入 make test）
client-check-rn: client-build-rn client-tsc

# 客户端 Jest 单测（services + utils + store + components 端无关层）
# 首次需先 `cd client && pnpm install` 拉 jest / @testing-library/* / babel-jest 等
client-test:
	cd client && pnpm test

client-test-watch:
	cd client && pnpm test:watch

client-test-coverage:
	cd client && pnpm test:coverage

# CI 入口：单 worker / silent / 失败即返回非 0
client-test-ci:
	cd client && pnpm test:ci

# ==================== 健康检查 ====================
check:
	@curl -s http://localhost:8000/v1/health | python3 -m json.tool || echo "✗ 后端未启动或异常"

# ==================== 质量门 rollup（W6-T5） ====================
# make test：常规 PR/commit 前的全量单测 + lint + tsc
# make ci：在 test 基础上再跑 smoke（需 make up 已起真实 ai_engine）
test: backend-lint backend-test ai-engine-lint ai-engine-test client-check-rn client-test-ci
	@echo ""
	@echo "✓ backend + ai_engine + client（含 RN/tsc + Jest）全部绿"

ci: test ai-engine-smoke
	@echo ""
	@echo "✓ CI gate 全绿（含真实引擎 smoke）"

# ==================== W8-T4：测试环境部署 ====================
# 设计取舍：
#   - 复用同一份 .env.local；测试环境部署时 cp .env.test → .env.local 后改占位值
#   - 用 -f docker-compose.yml -f docker-compose.test.yml 叠加，避免维护重复 base
#   - 所有目标都接受 HOST 参数（生成证书 + 健康检查需要）

# 复用变量，省去每条命令都写一次
TEST_COMPOSE := docker compose -f docker-compose.yml -f docker-compose.test.yml --env-file .env.local

# CVM 规范化：`docker-compose.cvm.yml` 用 Compose merge `!reset` 去掉 backend/celery/ai_engine 宿主 bind
# 若在仓库根存在 `docker-compose.wechat-pay-key.yml`（从 docker-compose.wechat-pay-key.example.yml 复制并改 PEM 路径），自动叠加挂载私钥。
CVM_PAY_KEY_FLAGS := $(if $(wildcard docker-compose.wechat-pay-key.yml),-f docker-compose.wechat-pay-key.yml,)
CVM_COMPOSE := docker compose -f docker-compose.yml -f docker-compose.test.yml -f docker-compose.cvm.yml $(CVM_PAY_KEY_FLAGS) --env-file .env.local

deploy-cvm-up:
	@if [ ! -f docker-compose.cvm.yml ]; then \
		echo "✗ 未找到 docker-compose.cvm.yml"; exit 1; \
	fi
	@$(MAKE) deploy-check-cvm-pay ENV_FILE="$(or $(ENV_FILE),.env.local)"
	$(CVM_COMPOSE) up -d --build
	@echo ""
	@echo "✓ CVM 栈已更新（镜像内后端/引擎；详见 docs/release-notes/CVM-canonical-deploy.md）"

deploy-cvm-ps:
	$(CVM_COMPOSE) ps

deploy-cvm-logs:
	$(CVM_COMPOSE) logs -f --tail=200

# 路径 B：公钥装进 CVM → 此后 publish-backend-cvm 无密码（首次须在本机终端跑，会提示一次服务器口令）
setup-cvm-ssh-key:
	bash infra/deploy/setup-cvm-ssh-key.sh

# 在云服务器跑一次 migrate 即可（见文档）；本条仅打出路径
cvm-migrate-git-doc:
	@echo "云上 rsync→git：docs/release-notes/CVM-migrate-rsync-to-git.md"
	@echo "脚本（随仓库在云路径后）：bash infra/deploy/cvm-bootstrap-git-on-server.sh  （需 GIT_REPO_URL）"

# 从本 Mac 推到当前 CVM（优先使用 ~/.ssh/id_ed25519_birdie_golf）
publish-backend-cvm:
	bash infra/deploy/publish-backend-to-cvm.sh

publish-monitoring-cvm:
	bash infra/deploy/publish-monitoring-to-cvm.sh

# ---------------------------------------------------------------------------
# 极简发版：代码已在 Git 远端后，本条只 SSH 触发 CVM 上的 release-cvm-on-server.sh；
# 生产 .env.local 只在服务器维护，无需在 Mac 指定 ENV_FILE。
# 可调：DEPLOY_HOST=… GIT_BRANCH=… SKIP_GIT=1（无 .git / rsync 过渡期）
release-cvm: cvm-remote-release

# 从本机「零 SSH 手工登录」闭环：生产 env 预检 → push 当前分支 → release-cvm（免密依赖 setup-cvm-ssh-key）。
# 用法（示例）：
#   DEPLOY_HOST=ubuntu@你的公网IP ENV_FILE=$(HOME)/secrets/lingniao-prod.env make ship-cvm
# 说明：ENV_FILE 只用于 Mac 侧预检；远端固定拉 GIT_BRANCH=main（与 git push 一致）。
# 非 main 发版请手动 push 后：GIT_BRANCH=<分支或tag> make release-cvm
ship-cvm:
	@if [ -z "$(ENV_FILE)" ]; then \
	  echo "✗ ship-cvm 需要 ENV_FILE（生产 secrets，用于本机预检）。示例：" >&2; \
	  echo "  DEPLOY_HOST=ubuntu@x.x.x.x ENV_FILE=\$$HOME/secrets/lingniao-prod.env make ship-cvm" >&2; \
	  echo "  须已执行：DEPLOY_HOST=… make setup-cvm-ssh-key" >&2; \
	  exit 1; \
	fi
	@if [ ! -f "$(ENV_FILE)" ]; then echo "✗ 找不到 $(ENV_FILE)" >&2; exit 1; fi
	@cb="$$(git rev-parse --abbrev-ref HEAD)"; \
	if [ "$$cb" != "main" ]; then \
	  echo "✗ ship-cvm 仅在 **main** 上执行（与远端默认 GIT_BRANCH=main 对齐）。当前分支：$$cb" >&2; \
	  echo "  请先合并到 main，或改用：git push origin $$cb && DEPLOY_HOST=… GIT_BRANCH=$$cb CVM_LOCAL_PREFLIGHT=1 ENV_FILE=$(ENV_FILE) make release-cvm" >&2; \
	  exit 1; \
	fi
	$(MAKE) cvm-preflight ENV_FILE="$(ENV_FILE)"
	git push origin main
	CVM_LOCAL_PREFLIGHT=0 GIT_BRANCH=main $(MAKE) release-cvm

cvm-deploy-help:
	bash scripts/deploy-cvm.sh

cvm-deploy-dry-run:
	bash scripts/deploy-cvm.sh --dry-run

cvm-env-preflight:
	bash scripts/deploy-cvm.sh --local-preflight --env-file="$(or $(ENV_FILE),.env.local)"

cvm-preflight:
	@$(MAKE) deploy-check-env ENV_FILE="$(or $(ENV_FILE),.env.local)"
	@$(MAKE) deploy-check-cvm-pay ENV_FILE="$(or $(ENV_FILE),.env.local)"
	@echo ""
	@echo "✓ cvm-preflight：env + 微信支付 compose 自检完成。"
	@echo "  可选：DOMAIN=… make verify-weapp-https   ｜发版后 make cvm-smoke DOMAIN=…"

cvm-preflight-tls: cvm-preflight
	@$(MAKE) verify-weapp-https DOMAIN="$(or $(DOMAIN),api.birdieai.cn)"

cvm-remote-release:
	bash scripts/cvm-remote-release.sh

# 从 Mac 稳妥发版：生产 ENV_FILE → 预检 →（默认）TLS → SSH 远端整包脚本（Compose + alembic + nginx）。
# ENV_FILE：须为生产 secrets，勿用含 trycloudflare/ngrok 的开发 .env。
# SKIP_TLS=1：跳过 verify-weapp-https。
# DRY_RUN=1：预检(+TLS) 后退出，不发 SSH。
# 其他：GIT_BRANCH / SKIP_GIT / DEPLOY_HOST 随 shell 传给 cvm-remote-release.sh（与子进程环境一致）。
cvm-stable-from-mac:
	@if [ -z "$(ENV_FILE)" ]; then \
	  echo "✗ cvm-stable-from-mac 必须指定 ENV_FILE=…（示例里的「/你的/生产secrets路径」需换成本机真实路径，不能直接照抄）" >&2; \
	  exit 1; \
	fi
	@if [ ! -f "$(ENV_FILE)" ]; then \
	  echo "✗ 找不到文件：$(ENV_FILE)" >&2; \
	  echo "  文档里的 /你的/生产secrets路径.env 只是示意，请在命令里换成你真的用来放密钥的文件。" >&2; \
	  echo "  示例：ENV_FILE=$(HOME)/secrets/xiaoniao-prod.env  （把文件名改成你自己的）" >&2; \
	  echo "  或从访达把文件拖进终端，会自动变成绝对路径。" >&2; \
	  exit 1; \
	fi
	@$(MAKE) cvm-preflight ENV_FILE="$(ENV_FILE)"
	@if [ "$(SKIP_TLS)" != "1" ]; then $(MAKE) verify-weapp-https DOMAIN="$(or $(DOMAIN),api.birdieai.cn)"; fi
	@if [ "$(DRY_RUN)" = "1" ]; then \
	  echo ""; \
	  echo "✓ DRY_RUN=1：预检（与 TLS，若未设 SKIP_TLS=1）已完成，未执行 SSH。"; \
	  exit 0; \
	fi
	@echo ""
	@echo "→ SSH 执行远端 infra/deploy/release-cvm-on-server.sh（须已 git push；rsync-only 过渡期见 SKIP_GIT=1）"
	@bash scripts/cvm-remote-release.sh

cvm-smoke:
	DOMAIN="$(or $(DOMAIN),api.birdieai.cn)" \
	TOKEN="$(TOKEN)" LOGIN_CODE="$(LOGIN_CODE)" CURL_EXTRA="$(CURL_EXTRA)" \
	  bash scripts/cvm-smoke.sh

test-certs:
	@if [ -z "$(HOST)" ]; then \
		echo "用法：make test-certs HOST=测试主机或IP"; \
		echo "  例：make test-certs HOST=test.birdieai.example.com"; \
		echo "  例：make test-certs HOST=123.45.67.89"; \
		exit 1; \
	fi
	bash infra/test/gen-certs.sh $(HOST)

# 自检 .env.local 是否还带尖括号/穿透占位（在仓库根或 CVM compose 目录执行）
deploy-check-env:
	bash infra/deploy/quick-check-env-local.sh "$(or $(ENV_FILE),.env.local)"

deploy-check-cvm-pay:
	bash infra/deploy/check-cvm-pay-mount.sh "$(or $(ENV_FILE),.env.local)"

# ---------------------------------------------------------------------------
# 紧急队列 U-1～U-6 巡检脚本（docs/19 §二）
# 默认走远端 CVM（DEPLOY_HOST=… BIRDIE_CVM_KEY=… 可覆盖）；本机栈用 LOCAL=1。
# ---------------------------------------------------------------------------

# U-1：Celery beat + expire_stale_pending_orders 派发
check-cvm-beat:
	bash infra/deploy/check-celery-beat.sh

# U-2：COS / CDN 真桶冒烟（PUT/HEAD/GET/CORS/DELETE，可选 CDN_HOST）
# 用法：COS_BUCKET=foo COS_REGION=ap-shanghai COS_SECRET_ID=… COS_SECRET_KEY=… make check-cos-smoke
check-cos-smoke:
	bash scripts/cos-smoke.sh

# U-3：从 client/.env.production(.local) + .env.local 汇集 host，
# 逐个跑 verify-weapp-https-readiness.sh，并输出「服务器域名」登记清单
check-weapp-domains:
	bash scripts/check-weapp-domains.sh

# U-4：校验 WECHAT_PAY_NOTIFY_URL / REFUND_NOTIFY_URL 路径与后端路由一致
# 用法：ENV=.env.local make check-pay-callbacks
check-pay-callbacks:
	bash scripts/check-payment-callbacks.sh

# U-0：.env.local 隧道 URL → api.birdieai.cn 同源（仅当检测到 trycloudflare/ngrok）
check-heal-local-env:
	bash scripts/heal-local-env-tunnels.sh

# U-1～U-4 一键巡检（发版前 5 分钟；无需人工逐步敲命令）
check-preflight: check-heal-local-env check-pay-callbacks check-weapp-domains check-cos-smoke check-cvm-beat
	@printf '\n\033[32m✓ check-preflight：U-0～U-4 已全部执行（COS 未配密钥时 U-2 自动跳过）\033[0m\n'

deploy-test:
	@if [ ! -f infra/test/certs/fullchain.pem ] || [ ! -f infra/test/certs/privkey.pem ]; then \
		echo "✗ 未找到 infra/test/certs/fullchain.pem / privkey.pem"; \
		echo "  先执行：make test-certs HOST=你的测试域名或IP（自签）"; \
		echo "  或：Let's Encrypt → infra/deploy/README.md"; \
		exit 1; \
	fi
	@if [ ! -f .env.local ]; then \
		echo "✗ 未找到 .env.local"; \
		echo "  先执行：cp .env.test .env.local && 编辑填入真实密钥"; \
		exit 1; \
	fi
	$(TEST_COMPOSE) up -d --build
	@echo ""
	@echo "✓ 测试栈已起："
	@echo "  • HTTPS 入口（把证书的 HOST 代入）： https://YOUR_PUBLIC_HOST/v1/health"
	@echo "  • 微信小程序体验版须可信证书：make issue-le-cert EMAIL=…（见 infra/deploy/README.md）"
	@echo "  • MinIO 控制台（仅本机）：http://127.0.0.1:9002（测试栈 compose.test 映射；SSH 隧道见 docker-compose.test.yml）"
	@echo "  • 查日志：make test-logs"

issue-le-cert:
	@if [ -z "$(EMAIL)" ]; then \
		echo "用法：make issue-le-cert EMAIL=you@example.com DOMAIN=api.birdieai.cn"; \
		echo "  前置：栈已启动（nginx 监听 80，且挂载 infra/test/acme-webroot）"; \
		exit 1; \
	fi
	bash infra/deploy/issue-le-cert-webroot.sh "$(EMAIL)" "$(or $(DOMAIN),api.birdieai.cn)"

sync-le-certs:
	bash infra/deploy/sync-le-certs-from-letsencrypt.sh "$(or $(DOMAIN),api.birdieai.cn)"

renew-le-cert:
	bash infra/deploy/renew-le-cert-docker.sh "$(or $(DOMAIN),api.birdieai.cn)"

verify-weapp-https:
	@if [ -z "$(DOMAIN)" ]; then \
		echo "用法：make verify-weapp-https DOMAIN=api.example.com"; \
		echo "  可选：STRICT_HEALTH=1 make verify-weapp-https DOMAIN=…   （要求 /v1/health 必须 2xx）"; \
		exit 1; \
	fi
	bash infra/deploy/verify-weapp-https-readiness.sh "$(DOMAIN)"

test-logs:
	$(TEST_COMPOSE) logs -f --tail=200

test-ps:
	$(TEST_COMPOSE) ps

test-restart:
	$(TEST_COMPOSE) restart

test-health:
	@if [ -z "$(HOST)" ]; then \
		echo "用法：make test-health HOST=<test-host-or-ip>"; \
		exit 1; \
	fi
	@curl -fk -m 5 https://$(HOST)/v1/health \
		&& echo "" && echo "✓ /v1/health 返回 200" \
		|| (echo "✗ /v1/health 检查失败"; exit 1)

test-reset:
	@echo "⚠️  这会删除测试环境所有容器和数据卷（PG/Redis/MinIO）。"
	@read -p "继续？(y/N) " yn; [ "$$yn" = "y" ] || (echo "取消"; exit 1)
	$(TEST_COMPOSE) down -v --remove-orphans
	@echo "✓ 测试栈已彻底清理"
