# API 联调示例（curl collection）

> 用途：新同学/后端 QA 在不依赖小程序客户端的情况下，验证后端 M1 链路是否通。
> 所有脚本默认走本地 `make up` 启动的后端（`http://localhost:8000`，mock 微信登录）。

## 前置条件

```bash
make up            # 后端 + Postgres + Redis + MinIO 起来
make check         # 返回 {"status":"ok"} 即可继续
```

## 脚本一览

| 脚本 | 覆盖场景 | 预期时长 |
|------|----------|----------|
| [`users-auth.sh`](./users-auth.sh) | 登录 → me → onboarding → 跳过 → 拒绝反向置 false → 编辑档案 → 刷新 token | < 10 秒 |
| [`analyses-lifecycle.sh`](./analyses-lifecycle.sh) | 登录 → upload-token（40005/40004/正常）→ MinIO 直传 → 创建任务 → status → report 预期 409 → 列表分页/筛选（**M2-T1**：任务停在 pending，T2 合入后会自动跑完） | < 15 秒 |

## 运行方式

```bash
bash docs/api-examples/users-auth.sh
# 或指定后端地址
API_BASE_URL=http://localhost:8000 bash docs/api-examples/users-auth.sh
```

脚本以 `set -e` 模式运行，任一步骤 HTTP code 非预期即终止。
