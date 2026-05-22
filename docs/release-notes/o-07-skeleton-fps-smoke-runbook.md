# O-07 骨骼叠加 FPS · 真机 Smoke Runbook

> **前置**：CVM `ai_engine` 已发版至含 `MIN_SKELETON_PLAYBACK_FPS` 的 commit（v1.2.3+）；小程序体验版 **1.2.3**。

---

## 1. 服务端快速验（发版后）

```bash
# CVM 或本机 SSH
cd ~/lingniao-golf
git rev-parse --short HEAD   # 应 ≥ b1f676a

docker compose -f docker-compose.yml -f docker-compose.test.yml -f docker-compose.cvm.yml \
  --env-file .env.local exec -T ai_engine \
  uv run pytest tests/test_skeleton_fps.py -q
```

`/v1/health` 中 `ai_engine.mock_mode` 应为 `false`。

---

## 2. 真机 Smoke（约 10 分钟）

| # | 步骤 | 通过标准 |
|---|------|----------|
| 1 | 体验版 **1.2.3**，侧向全身 **3～10s** 挥杆，光线充足 | 上传成功，进入等待页 |
| 2 | 等待分析完成 → 打开**新报告**（须本次上传，旧报告无效） | 报告页视频下方 **「原片 \| 骨骼叠加」** 可切换 |
| 3 | 默认 **1x** 播放整段 | 骨骼线跟身，无明显「幻灯片式」跳帧 |
| 4 | 切 **0.5x** 慢放 | 仍连贯，可辨骨骼点 |
| 5 | 点击阶段条 **上杆 / 击球** | 视频 seek 正常，骨骼仍叠加 |
| 6 | （可选）故意用极暗/糊视频 | v1.2.0 params 阻断或软警告；不应出现无骨骼的原片冒充叠加 |

**失败时记录**：分析 ID、机型、微信基础库版本、是否 Wi‑Fi、录屏 5s。

---

## 3. 与「分数低」区分

O-07 只验 **播放流畅 + 骨骼片存在**；**30 分 / 站位 0** 属评分引擎，不在本 Runbook 验收范围。

---

## 4. 签字

| 角色 | 结果 | 日期 |
|------|------|------|
| 产品/测试 | ☐ Pass / ☐ Fail | |
