# O-07 骨骼叠加 FPS · 真机 Smoke Runbook

> **前置**
>
> - CVM `ai_engine` ≥ commit `b1f676a`（v1.2.3+ FPS 编码链；v1.2.4+ 报告页 **原片 | 骨骼叠加** 切换）
> - 小程序体验版 ≥ **1.2.4**（推荐 **1.2.7+** 含示范视频播放优化，与本 Runbook 无冲突）
> - `/v1/health` → `services.ai_engine.status=ok` 且 `ai_engine.mock_mode=false`

---

## 1. 服务端快速验（发版后，约 3 分钟）

```bash
# CVM SSH
cd ~/lingniao-golf   # 或实际部署目录
git rev-parse --short HEAD   # 应 ≥ b1f676a（ai_engine FPS 链）

# ai_engine 单测
docker compose -f docker-compose.yml -f docker-compose.test.yml -f docker-compose.cvm.yml \
  --env-file .env.local exec -T ai_engine \
  uv run pytest tests/test_skeleton_fps.py -q

# 健康探针
curl -sS "https://api.birdieai.cn/v1/health" | python3 -m json.tool | head -40
```

**通过标准**：pytest 全绿；`ai_engine.mock_mode` 为 `false`；`services.ai_engine` 为 `ok`。

---

## 2. 真机 Smoke（约 10 分钟）


| #   | 步骤                                    | 通过标准                                       |
| --- | ------------------------------------- | ------------------------------------------ |
| 1   | 体验版 **≥1.2.4**，侧向全身 **3～10s** 挥杆，光线充足 | 上传成功，进入等待页                                 |
| 2   | 等待分析完成 → 打开**本次新报告**（旧报告无效）           | 报告页视频下方可见 **「原片 | 骨骼叠加」** pill 切换（v1.2.4+） |
| 3   | 默认 **骨骼叠加** + **1x** 播放整段             | 骨骼线跟身，无明显「幻灯片式」跳帧                          |
| 4   | 切 **原片** 再切回 **骨骼叠加**                 | 切换正常，骨骼片仍可播                                |
| 5   | 切 **0.5x** 慢放（骨骼模式）                   | 仍连贯，可辨骨骼点                                  |
| 6   | 点击阶段条 **上杆 / 击球**                     | seek 正常，骨骼仍叠加                              |
| 7   | （可选）极暗/糊视频走 params 页                  | v1.2.0 硬阻断或软警告；**不应**用无骨骼原片冒充叠加            |
| 8   | （可选）训练 Tab 展开任务看 **动作参考** 视频          | v1.2.8+ 可播放；与本项独立，失败不阻塞 O-07               |


**失败时记录**（填 §4 签字表）：

- 分析 ID（`ana_…`）
- 机型 / 系统版本 / 微信基础库
- 网络（Wi‑Fi / 4G）
- 录屏 5s 或截图

---

## 3. 与「分数低」区分

O-07 只验 **播放流畅 + 骨骼片存在 + 切换可用**。**综合分偏低 / 站位 0 分** 属评分引擎（ENG-04 标定），不在本 Runbook 验收范围。

---

## 4. 签字表


| 字段                    | 内容                                             |
| --------------------- | ---------------------------------------------- |
| 体验版版本                 | 例：1.2.7                                        |
| 后端 / ai_engine commit | 例：`721b601` / 容器内 `git rev-parse --short HEAD` |
| 测试分析 ID               | 例：`ana_xxxxxxxx`                               |
| 测试机型                  | IPHONE12PRO                                    |
| 微信基础库                 | 开发者工具或真机「关于」页                                  |
| 网络环境                  | Wi‑Fi                                          |



| 角色                   | 结果     | 日期        | 备注                              |
| -------------------- | ------ | --------- | ------------------------------- |
| 工程                   | ☐ Pass | 2026.5.22 | ai_engine pytest + health       |
| 产品/测试                | ☐ Pass | 2026.5.22 | 真机 §2 步骤 1～6                    |
| 产品签字（`docs/01` O-07） | ☐ Pass | 2026.5.22 | Pass 后可在 `docs/01` §4.3 脚注补真机日期 |


**Fail 处理**：保留分析 ID → 查 CVM `ai_engine` 日志 `skeleton_fps_below_min` / MinIO 是否有 `skeleton_*.mp4` → 必要时回退 mock 排查见 `[v1.2.0-real-pipeline-runbook.md](./v1.2.0-real-pipeline-runbook.md)`。

---

## 5. 关联文档

- 客户端切换 UX：`[v1.2.4-release-notes.md](./v1.2.4-release-notes.md)`
- 引擎运维：`[v1.2.0-real-pipeline-runbook.md](./v1.2.0-real-pipeline-runbook.md)`
- PLAN-ID：**O-07** / **Q-B4**（`[docs/19` §6.5](../19-产品开发迭代计划-当前队列.md#65-docs01-未勾--部分完成--plan-id对照表)）

