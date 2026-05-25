# P2-M10-04 · drill 库扩到 25-30 条（推杆 / 切杆类目）· 启动包（W26 起跑）

> 版本：v0.1（2026-05-25）
> 上游真源：[`docs/23 §6.4`](../23-二期可编码规格说明书.md#64-p2-m10-04--drill-库扩到-25-30-条增加推杆--切杆类目)
> 前置：DEP-02 教练 BD + DEP-03 拍摄团队

---

## 一、文档目的与边界

为 **P2-M10-04** 落地 W26-W34 教研 + 内容 + 后端 SOP，drill 库从 13 条扩到 25-30 条（新增推杆 ≥5 / 切杆 ≥3）。

### 边界（不做）

- 不修改 docs/22/23 字段
- 不进入 M12 球手类专属对照（独立任务）

---

## 二、现状盘点

```
client/src/data/drillLibrary.ts
  → 13 条 drill；无 category 区分
backend/app/models/training.py: Drill
  → 无 category 字段
client/src/constants/drillVideos.ts
  → DRILL_VIDEO_ALIGNED_IDS：当前 hotfix 期为空
```

### 缺口（vs docs/23 §6.4 FR）

5 个 FR 全部新增。

---

## 三、模块设计

### 3.1 新增 / 改造

| 模块 | 路径 | 工程量 |
| --- | --- | --- |
| Migration 加 category | `0022_drills_category.py` | 0.2 PW |
| Drill 模型 | `models/training.py` 加 category | 0.2 PW |
| 教研 SOP | 12-17 条新 drill 撰写 + 评审 | 1.5 PW |
| 拍摄 | 12-17 段 30-60s 示范视频 | 2 PW |
| 客户端 | `drillLibrary.ts` 扩 + `DRILL_VIDEO_ALIGNED_IDS` 灰度名单 | 0.5 PW |
| 联动 M10-01 报告 | 推杆 issue 推推杆 drill | 0.3 PW |
| 单测 | tests | 0.3 PW |

**合计：~5 PW**（与 docs/23 §6.4 持平）

### 3.2 新 drill 数量分配

| 类目 | 数量 | 范例 |
| --- | --- | --- |
| putting（≥5） | 5-7 | 单手推杆 / 距离控制 / 钟摆推杆 / 杯口直推 / 双手分离推杆 |
| chipping（≥3） | 3-5 | 短杆击球点 / 高抛切杆 / 平推切杆 |
| full_swing 补 ≥4 | 4-5 | impact bag / 阶段定位 / mirror drill 等 |

### 3.3 上线灰度

每条 drill：
1. 后端 `drills` 表 INSERT（category=...）
2. 视频 COS 上传
3. `DRILL_VIDEO_ALIGNED_IDS` 加入 → 灰度名单（部分用户先体验）
4. 7 天无负反馈 → 全量开放

### 3.4 与 M10-05 联动

drill.category 字段供 M10-05 训练计划生成消费。

---

## 四、字段 v0.1

```sql
ALTER TABLE drills ADD COLUMN category VARCHAR(20) DEFAULT 'full_swing';
-- enum: full_swing | putting | chipping
CREATE INDEX idx_drill_cat ON drills(category);
```

---

## 五、验证数据

- drill 总数 ≥25（AC-1）
- putting ≥5 / chipping ≥3（AC-2）
- 每条专属视频（AC-3）
- ALIGNED_IDS 全量纳入（AC-4）

---

## 六、W26-W34 周计划

| 周 | 任务 |
| --- | --- |
| W26 | category migration + 模型 |
| W27-W28 | 教研撰写 12-17 条 |
| W29-W31 | 拍摄 12-17 段 |
| W32 | 客户端 + ALIGNED_IDS 灰度 |
| W33-W34 | 全量开放 + 监控 |

---

## 七、责任 / 风险 / 验收

### 责任

| 角色 | 责任 |
| --- | --- |
| 教研 | 内容撰写 + 评审 |
| 拍摄 | DEP-03 团队 |
| 后端 | category + 数据 |
| 客户端 | 库扩 + ALIGNED |

### 风险

| ID | 风险 | 兜底 |
| --- | --- | --- |
| R-01 | 拍摄延期 | 文字步骤先上；视频灰度持续补 |
| R-02 | 视频质量参差 | drill-demo-video-revamp 规范 + 走查 |
| R-03 | 推杆 drill 与 M10-01 报告匹配率低 | M10-05 推荐算法兜底 |
| R-04 | 视频 >8MB | 720p + H.264 标准压缩 |

### AC

- [ ] AC-1 总数 ≥25
- [ ] AC-2 推杆 ≥5 / 切杆 ≥3
- [ ] AC-3 每条专属视频
- [ ] AC-4 ALIGNED_IDS 全量

---

## 八、附录

| 任务 | 关系 |
| --- | --- |
| P2-M10-01/02 | 推荐 drill 来源 |
| P2-M10-05 训练计划 | 消费 category |
| 一期 drillLibrary | 扩展 |

---

## 九、变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-05-25 | 初版 |
