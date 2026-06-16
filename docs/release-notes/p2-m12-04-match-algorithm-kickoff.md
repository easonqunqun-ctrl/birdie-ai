# P2-M12-04 · 匹配算法（"和你最像的职业是 X"）· 启动包（W30 起跑）

> 版本：v0.1（2026-05-25）
> 上游真源：[`docs/23 §8.4`](../23-二期可编码规格说明书.md#84-p2-m12-04--匹配算法和你最像的职业是-x)
> 前置：P2-M7-08 新特征 + P2-M12-02 球手 features_snapshot

---

## 一、文档目的与边界

为 **P2-M12-04** 落地 W30-W34 算法 SOP，给报告页加"和你最像的职业球手"匹配卡片。

### 边界（不做）

- 不实现并排叠加（M12-05）
- 不修改 docs/22/23 字段

---

## 二、现状盘点

- M7-08 新特征已落库（tempo / pressure / kinematic / head / rhythm）
- M12-02 球手 features_snapshot 已落
- 一期报告页无"匹配"卡片

### 缺口

6 个 FR 全部新增。

---

## 三、模块设计

### 3.1 新增

| 模块 | 路径 | 工程量 |
| --- | --- | --- |
| Service | `services/pro_match_service.py` | 1.2 PW |
| API | POST /v1/pros/match + GET /history | 0.5 PW |
| 算法 | cosine + 加权欧氏距离对比试验 | 1 PW |
| 报告卡片 UI | `pages/analysis/report.tsx` 加 ProMatchCard | 0.5 PW |
| 单测 | tests | 0.3 PW |
| 教研验证 | 100 段人工评分 | 0.5 PW |

**合计：~4 PW**

### 3.2 匹配特征向量

```python
features = [
    user_profile.height_cm / 200,
    1 if user.handedness == 'right' else 0,
    new_features.tempo_ratio / 4,
    new_features.pressure_shift_quality / 100,
    new_features.kinematic_sequence_quality / 100,
    new_features.head_stability / 1000,
]
# 与每位球手 same club_category 的 clip features 计算 cosine
```

### 3.3 同 club_category 优先

```python
candidates = filter_clips_by_category(club_category)  # 优先
if len(candidates) < 3:
    candidates += filter_all_clips()  # fallback
```

### 3.4 返回结构

```jsonc
{
  "matches": [
    {
      "player_id": "...", "player_name_zh": "斯科蒂·谢夫勒",
      "clip_id": "...", "similarity": 0.78,
      "dimension_gaps": {
        "tempo": -0.1, "head_stability": -0.3, ...
      }
    },
    // top 3
  ]
}
```

---

## 四、字段 v0.1

```
POST /v1/pros/match Body: { analysis_id }
GET  /v1/pros/match/history?page=
```

---

## 五、验证数据

- 100 段人评准确率 ≥70%（AC-2）
- 同 club_category 优先策略生效（AC-3）
- 匹配响应 <1s

---

## 六、W30-W34 周计划

| 周 | 任务 |
| --- | --- |
| W30 | 算法 + 试验 |
| W31 | service + API |
| W32 | 报告 UI 卡片 |
| W33 | 教研 100 段验证 |
| W34 | 灰度 + AC |

---

## 七、责任 / 风险 / 验收

### 责任

| 角色 | 责任 |
| --- | --- |
| 算法 Lead | 算法 |
| 后端 | service / API |
| 客户端 | 卡片 UI |
| 教研 | 100 段人评 |

### 风险

| ID | 风险 | 兜底 |
| --- | --- | --- |
| R-01 | 球手库 <20 位匹配差 | M12-02 持续扩；最少 10 |
| R-02 | cosine 与人评偏差 | 多算法对比试验 |
| R-03 | 同 category 不够 | fallback 跨 category |
| R-04 | "相似度 78%"被理解为评分 | 文案"相似度" |

### AC

- [ ] AC-1 卡片上线
- [ ] AC-2 ≥70% 人评准确
- [ ] AC-3 同 category 优先

---

## 八、附录

| 任务 | 关系 |
| --- | --- |
| P2-M7-08 | 特征源 |
| P2-M12-02 | clip 特征源 |
| P2-M12-05 | 并排页消费匹配结果 |

---

## 九、变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-05-25 | 初版 |
