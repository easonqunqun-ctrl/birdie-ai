# P2-M12-05 · 并排叠加播放 + 差距维度雷达图 · 启动包（W32 起跑）

> 版本：v0.1（2026-05-25）
> 上游真源：[`docs/23 §8.5`](../23-二期可编码规格说明书.md#85-p2-m12-05--并排叠加播放--差距维度雷达图)
> 前置：P2-M12-04 匹配 + 一期 Canvas / VideoPlayer 组件

---

## 一、文档目的与边界

为 **P2-M12-05** 落地 W32-W36 客户端 SOP，提供"你 vs 球手"并排对比页（关键帧对齐 + 6 维雷达）。

### 边界（不做）

- 不实现追平演化（M12-08）
- 不动一期视频组件（仅复用）

---

## 二、现状盘点

- M12-04 输出 dimension_gaps（6 维）
- 一期 VideoPlayer + ProgressLineChart 可复用
- key_phase_timestamps 由 M12-02 落 features_snapshot 内

### 缺口

6 个 FR 全部新增。

---

## 三、模块设计

### 3.1 新增

| 模块 | 路径 | 工程量 |
| --- | --- | --- |
| 并排播放页 | `pages/pros/compare/[match_id].tsx` | 1.5 PW |
| 双 Video 同步 | `components/SyncedVideos.tsx`（新） | 1 PW |
| 雷达图 | `components/RadarChart.tsx`（新 + canvas） | 0.7 PW |
| 帧步进控件 | `components/FrameStepper.tsx` | 0.5 PW |
| 单测 | tests | 0.3 PW |

**合计：~4 PW**

### 3.2 关键帧对齐算法

```typescript
const userImpactFrame = analysis.phases.impact.frame
const proImpactFrame = clip.key_phase_timestamps.impact_frame
// seek 两侧视频到 impact，加上对齐偏移
const offsetSec = (userImpactFrame - proImpactFrame) / fps
syncedVideos.alignAt('impact', offsetSec)
```

### 3.3 6 维雷达

| 维度 | 数据 |
| --- | --- |
| 节奏 | tempo_ratio |
| 重心 | pressure_shift_quality |
| 接力 | kinematic_sequence_quality |
| 头部稳定 | head_stability |
| 站位 | setup score |
| 击球点 | impact score |

```typescript
<RadarChart
  user={userScores}
  pro={proScores}
  axisLabels={['节奏', '重心', '接力', '头部', '站位', '击球点']}
/>
```

### 3.4 帧步进同步

- 0.5x / 1x / 2x 控件
- 同时 seek 锚点
- 延迟 ≤200ms（AC-3）

---

## 四、字段 v0.1

无新 API；消费 M12-04 + features_snapshot。

---

## 五、验证数据

- 关键帧对齐（AC-1）
- 6 维与 M7 V2 特征 1:1（AC-2）
- 同步流畅 ≤200ms（AC-3）

---

## 六、W32-W36 周计划

| 周 | 任务 |
| --- | --- |
| W32 | 并排页骨架 |
| W33 | SyncedVideos |
| W34 | RadarChart |
| W35 | FrameStepper + 单测 |
| W36 | 灰度 + AC |

---

## 七、责任 / 风险 / 验收

### 责任

| 角色 | 责任 |
| --- | --- |
| 客户端 | UI |
| 设计 | 雷达图视觉 |

### 风险

| ID | 风险 | 兜底 |
| --- | --- | --- |
| R-01 | 双视频同步延迟 | requestAnimationFrame + offset 补偿 |
| R-02 | 雷达图 canvas RN 兼容性 | adapters 分叉；MVP 期小程序优先 |
| R-03 | key_phase_timestamps 缺失 | 降级首帧对齐 |

### AC

- [ ] AC-1 关键帧对齐
- [ ] AC-2 6 维 1:1
- [ ] AC-3 ≤200ms

---

## 八、附录

| 任务 | 关系 |
| --- | --- |
| P2-M12-04 | 数据源 |
| P2-M12-08 演化 | 雷达图基础 |
| P2-M7-08 | 6 维特征源 |

---

## 九、变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-05-25 | 初版 |
