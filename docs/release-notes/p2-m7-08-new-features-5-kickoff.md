# P2-M7-08 · 新特征 5 个（节奏 / 节拍稳定 / 重心 / 接力 / 头部稳定）· 启动包（W26 起跑）

> 版本：v0.1（2026-05-25）
> 上游真源：[`docs/23 §3.8`](../23-二期可编码规格说明书.md#38-p2-m7-08--新特征-5-个节奏--节拍稳定--重心--接力--头部稳定)
> 前置：[`p2-m7-07-phase-segmentation-v2-kickoff.md`](./p2-m7-07-phase-segmentation-v2-kickoff.md)（阶段边界）+ [`p2-m7-14-engine-version-ab-kickoff.md`](./p2-m7-14-engine-version-ab-kickoff.md)（灰度）

---

## 一、文档目的与边界

为 **P2-M7-08** 落地 W26-W34 算法 + LLM SOP，明确 5 个新特征的计算公式、JSONB schema、报告 UI 折叠区设计、LLM 引用。

### 边界（不做）

- 不修改 docs/22/23/05 字段
- 不改一期 15 特征
- 不实现 LLM 文案差异化（M7-16）；本任务仅产数据

---

## 二、现状盘点

一期 15 特征已覆盖姿态 / 角度类指标，**没有**：

- 节奏稳定性（多次挥杆方差）
- 重心转移质量
- 运动链接力时序
- 头部稳定方差量化

### 缺口（vs docs/23 §3.8 FR）

5 个特征全部新增；JSONB schema 已在 docs/03 §9.1 拟。

---

## 三、模块设计

### 3.1 新增

| 模块 | 路径 | 工程量 |
| --- | --- | --- |
| 5 特征计算 | `ai_engine/app/pipeline/features_v2.py`（新） | 3 PW |
| JSONB 写入 | `real_pipeline.py` 改 | 0.5 PW |
| LLM 引用 | `chat_prompt.py` 改 | 1 PW |
| 报告 UI 折叠区 | `pages/analysis/report.tsx` | 2 PW |
| 单测 | tests | 1.5 PW |
| 文档 / buffer | — | 2 PW |

**合计：~10 PW**（与 docs/23 §3.8 持平）

### 3.2 5 个特征公式（与 docs/05 §8.3 对齐）

| 特征 | 计算 | 单位 | ideal |
| --- | --- | --- | --- |
| `tempo_ratio` | backswing_frames / downswing_frames | ratio | 2.5-3.5（3:1 黄金） |
| `tempo_consistency` | 多次挥杆 tempo 标准差 | — | < 0.3 |
| `pressure_shift_quality` | 足部 y 偏移 / 髋部 x 偏移 score | 0-100 | > 70 |
| `kinematic_sequence_quality` | pelvis→torso→arms→wrists 速度峰时差合理性 | 0-100 | > 75 |
| `head_stability` | 鼻关键点位移方差 | px²（@720p） | < 400 |

每特征输出：

```jsonc
{
  "value": 2.8,
  "score": 88,
  "narrative": "节奏接近黄金比例 3:1，下杆爆发力较好"
}
```

### 3.3 报告 UI 折叠区

```tsx
<Accordion title="动力学详情" defaultExpanded={false}>
  {NEW_FEATURES.map(f => (
    <FeatureCard key={f.name} {...newFeatures[f.name]} />
  ))}
</Accordion>
```

埋点 `expand_dynamics_detail` 验证 ≥30% 展开率（AC-4）。

### 3.4 LLM prompt 注入

```
[新增] 5 个深层指标：
- 节奏 {tempo_ratio:.2f}（{narrative_tempo}）
- 节拍稳定 {tempo_consistency:.2f}
- 重心 {pressure_shift_quality}分
- 运动链 {kinematic_sequence_quality}分
- 头部稳定 {head_stability}px²

请在你的建议中至少引用 1 个新指标做点评。
```

---

## 四、字段 v0.1

### 4.1 `new_features_payload` JSONB schema

与 docs/03 §9.1 对齐。

### 4.2 API 响应

```jsonc
{
  "new_features": {
    "tempo_ratio": { "value": 2.8, "score": 88, "narrative": "..." },
    ...
  }
}
```

---

## 五、验证数据

- ECS v2 标杆：tempo_ratio 误差 < 0.2；head_stability 误差 < 5px（AC-2）
- LLM 报告至少 1 处引用新特征（AC-3）
- 展开率埋点 ≥30%（AC-4）

---

## 六、W26-W34 周计划

| 周 | 任务 |
| --- | --- |
| W26-W28 | 5 特征算法实现 + ECS 标定 |
| W29 | JSONB 写入 + LLM prompt 改造 |
| W30-W31 | 报告 UI 折叠区 + 单测 |
| W32 | 灰度 5% + LLM 引用 grep 验证 |
| W33-W34 | 灰度 25% → 50% + 展开率监控 |

---

## 七、责任 / 风险 / 验收

### 责任

| 角色 | 责任 |
| --- | --- |
| 算法 Lead | 5 特征算法 + 标定 |
| AI 工程 | JSONB + pipeline |
| LLM | prompt 模板 + grep |
| 客户端 | 折叠区 UI |

### 风险

| ID | 风险 | 兜底 |
| --- | --- | --- |
| R-01 | 5 特征中部分 ECS 数据不足 | 渐进上线，每特征单独灰度 |
| R-02 | 折叠区展开率 < 30% | UI 改进；首屏增加 1-2 个关键 |
| R-03 | LLM 引用空话（"节奏不错"） | grep 触发"节奏"必带数值 |

### AC

- [ ] AC-1：折叠区 5 特征可见
- [ ] AC-2：标杆误差达标
- [ ] AC-3：LLM 引用 ≥1
- [ ] AC-4：展开率 ≥30%

---

## 八、附录

| 任务 | 关系 |
| --- | --- |
| P2-M7-07 阶段 V2 | 提供阶段边界 |
| P2-M7-14 灰度 | engine_version=v2.0 |
| P2-M7-16 LLM 文案 | 消费 new_features narrative |
| P2-M12-01 球手镜头 | features_snapshot 对齐 |

---

## 九、变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-05-25 | 初版；5 特征公式 + JSONB + 报告 UI |
