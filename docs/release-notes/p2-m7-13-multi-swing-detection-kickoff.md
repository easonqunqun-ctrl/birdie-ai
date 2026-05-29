# P2-M7-13 · 试挥 / 多挥杆识别 · 启动包（W28 起跑）

> 版本：v0.1（2026-05-25）
> 上游真源：[`docs/23 §3.13`](../23-二期可编码规格说明书.md#313-p2-m7-13--试挥--多挥杆识别)
> 前置：P2-M7-07 阶段 V2 + P2-M7-14 灰度

---

## 一、文档目的与边界

为 **P2-M7-13** 落地 W28-W34 算法 + 客户端 SOP，识别多次挥杆 + 自动判别试挥，让用户从候选区间选要分析的那段。

### 边界（不做）

- 不修改 docs/22/23 字段（仅追加 selected_swing_index + 50122）
- 不支持 >5 段挥杆视频（报 50122）

---

## 二、现状盘点

- M7-07 V2 分段已输出多段候选（top→impact→follow 链）
- 一期 main.py 默认拿第一段；丢弃后续

### 缺口（vs docs/23 §3.13 FR）

5 个 FR 全部新增。

---

## 三、模块设计

### 3.1 新增

| 模块 | 路径 | 工程量 |
| --- | --- | --- |
| 多段候选输出 | `phases_v2.py` 加 candidates 字段 | 0.5 PW |
| 试挥判别 | `swing_classifier.py`（新） | 1 PW |
| main.py 路由 | 改 | 0.3 PW |
| 50122 错误码 | `errors.py` | 0.2 PW |
| 客户端候选 UI | `pages/analysis/select-swing.tsx`（新） | 1 PW |
| 缩略图生成 | ffmpeg 抽帧 | 0.5 PW |
| 单测 | tests | 0.5 PW |

**合计：~4 PW**（与 docs/23 §3.13 持平）

### 3.2 候选区间格式

```python
[
  {'start_frame': 30, 'end_frame': 120, 'is_practice': True, 'confidence': 0.92},
  {'start_frame': 180, 'end_frame': 270, 'is_practice': True, 'confidence': 0.88},
  {'start_frame': 330, 'end_frame': 450, 'is_practice': False, 'confidence': 0.95},
]
```

### 3.3 试挥判别

```python
def is_practice_swing(segment, pose) -> bool:
    # 启发式：无 impact 信号 / 杆头速度峰值低 / follow 不完整
    speed_peak = max(wrist_speeds[segment.start:segment.end])
    return speed_peak < PRACTICE_SPEED_THRESHOLD
```

### 3.4 客户端 UX

```
[视频拍摄完成]
检测到 3 段挥杆：
  □ 第 1 段 [试挥] 00:01-00:03 (缩略图)
  □ 第 2 段 [试挥] 00:06-00:08
  ☑ 第 3 段 [正式] 00:11-00:14 (缩略图)
[默认勾正式段 → 分析] [选其他段]
```

### 3.5 错误码 50122

```python
if len(candidates) > 5:
    raise EngineError(50122, '检测到超过 5 段挥杆，请重拍 1-3 段')
```

---

## 四、字段 v0.1

### 4.1 API

```
POST /v1/analyses
  Body: { ..., selected_swing_index: 2 }  // 默认第一段非试挥
Response: { ..., engine_warnings: ["检测到 3 段挥杆，已自动选择第 3 段"] }
```

---

## 五、验证数据

- 多挥杆视频识别准确率 ≥85%（AC-1）
- 用户能从候选选段（AC-2）
- 试挥自判 ≥80%（AC-3）
- >5 段 报 50122（AC-4）

---

## 六、W28-W34 周计划

| 周 | 任务 |
| --- | --- |
| W28 | candidates 输出 + 50122 |
| W29 | swing_classifier 判别 |
| W30 | 缩略图生成 |
| W31 | 客户端 select-swing UI |
| W32 | 单测 + ECS 验证 |
| W33 | 灰度 5% |
| W34 | 灰度 25% + AC 验收 |

---

## 七、责任 / 风险 / 验收

### 责任

| 角色 | 责任 |
| --- | --- |
| 算法 | 候选 + 试挥判别 |
| AI 工程 | 错误码 + ffmpeg |
| 客户端 | select-swing UI |

### 风险

| ID | 风险 | 兜底 |
| --- | --- | --- |
| R-01 | 试挥误判（正式判为试挥） | 默认全选；用户可主动选 |
| R-02 | 缩略图生成慢 | 异步 + 占位 loading |
| R-03 | 用户混淆 5 段上限 | 文案提示"建议 1-3 段" |
| R-04 | 候选 UI 加重决策疲劳 | 自动选第一段非试挥，可"再选一段" |

### AC

- [ ] AC-1 多段识别 ≥85%
- [ ] AC-2 候选可选
- [ ] AC-3 试挥自判 ≥80%
- [ ] AC-4 >5 段 50122

---

## 八、附录

| 任务 | 关系 |
| --- | --- |
| P2-M7-07 阶段 V2 | 多段输出 |
| P2-M7-14 灰度 | engine_version |

---

## 九、变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-05-25 | 初版 |
