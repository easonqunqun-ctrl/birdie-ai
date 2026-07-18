# PP-12 / PP-13 · J0 预检纪要（2026-07-18）

> 关联：[`product-priority-memo-2026-07-18.md`](./product-priority-memo-2026-07-18.md) · [`experience-version-smoke-runbook.md`](./experience-version-smoke-runbook.md)

## 自动化预检（AI 可代跑）

| 项 | 结果 | 备注 |
|----|------|------|
| `GET https://api.birdieai.cn/v1/health` | ✅ 200 | 发版后复核 ok；`mock_mode=false` |
| 仓库 `main` HEAD | `307fdc0` | Batch-J 1.2.36 已 push；CVM backend/worker/beat 已重建 |
| 客户端 | **1.2.36** CLI 已上传（约 1.3 MB） | 待 mp 选为体验版 + 真机确认 |
| 埋点白名单 | ✅ 容器内已含 `membership_view` / `upgrade_cta_click` | PP-05 |

## 须人工真机（阻塞 PP-12 关项）

在微信体验版（**关闭**「不校验合法域名」）按 smoke runbook 勾选：

1. **1.2.35/1.2.36 公测免费 P0**（首页 banner / 不限次 / 教练未登录合规）
2. **§D Phase2**：推杆 / 切杆 / 多挥 / yardage / 教练批注（有素材与教练账号时）

完成后：把 runbook 对应 `- [ ]` 改为 `- [x]`，并在本文件补一行「真机验收日期 / 操作人」。

## 真机验收栏（待填）

| 项 | 值 |
|----|-----|
| 验收日期 | |
| 体验版版本号 | |
| 操作人 | |
| P0 结论 | Pass / Fail |
| Phase2 §D 结论 | Pass / Partial / Skip |
| 失败项摘要 | |
