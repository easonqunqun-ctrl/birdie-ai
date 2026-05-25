# P2-M8-06 · 学员看板（100 学员规模 ≤2s 加载）· 启动包（W26 起跑）

> 版本：v0.1（2026-05-25）
> 上游真源：[`docs/23 §4.6`](../23-二期可编码规格说明书.md#46-p2-m8-06--学员看板100-学员规模-2s-加载)
> 前置：[`p2-m8-03-student-binding-kickoff.md`](./p2-m8-03-student-binding-kickoff.md)

---

## 一、文档目的与边界

为 **P2-M8-06** 落地 W26-W30 后端聚合 + 客户端 SOP，保证 100 学员规模学员看板 ≤2s 加载。

### 边界（不做）

- 不修改 docs/22/23/03/02 字段
- 不实现 M8-04 批注 / M8-05 派发逻辑（仅消费）
- 不动一期 swing_analyses / training_tasks 表

---

## 二、现状盘点

- 一期 swing_analyses / training_tasks 已有按 user_id 索引
- M8-03 提供 coach_student_relations active 关系
- M8-04 提供 analysis_annotations；M8-05 提供 coach_assigned_tasks
- 一期已有 Redis 7

### 缺口（vs docs/23 §4.6 FR）

5 个 FR 全部新增。

---

## 三、模块设计

### 3.1 新增

| 模块 | 路径 | 工程量 |
| --- | --- | --- |
| 聚合 service | `services/coach_dashboard_service.py` | 1.5 PW |
| API | GET /v1/coach/students / GET /v1/coach/students/{id}/dashboard | 0.5 PW |
| Redis 缓存 | `services/coach_dashboard_cache.py` | 0.5 PW |
| 教练侧 UI | `pages/coach/students/index.tsx` + `[id].tsx` | 1 PW |
| 性能压测 | `tests/perf/test_dashboard_p95.py` | 0.3 PW |
| 单测 | tests | 0.2 PW |

**合计：~4 PW**

### 3.2 聚合查询

```sql
SELECT
  csr.student_user_id,
  u.display_name, u.avatar_url,
  (SELECT COUNT(*) FROM swing_analyses WHERE user_id=csr.student_user_id AND created_at > NOW()-INTERVAL '7 days') AS analyses_7d,
  (SELECT MAX(created_at) FROM swing_analyses WHERE user_id=csr.student_user_id) AS last_analysis_at,
  (SELECT MAX(created_at) FROM analysis_annotations WHERE coach_user_id=:coach_id AND student_user_id=csr.student_user_id) AS last_annotation_at,
  (SELECT COUNT(*) FROM coach_assigned_tasks WHERE coach_user_id=:coach_id AND student_user_id=csr.student_user_id AND status IN ('assigned','started')) AS pending_tasks,
  -- "待回应"标记
  ((SELECT COUNT(*) FROM swing_analyses WHERE user_id=csr.student_user_id AND created_at > NOW()-INTERVAL '1 day') > 0
   AND COALESCE((SELECT MAX(created_at) FROM analysis_annotations WHERE coach_user_id=:coach_id AND student_user_id=csr.student_user_id), '1970-01-01') < NOW()-INTERVAL '24 hours'
  ) AS needs_response
FROM coach_student_relations csr
JOIN users u ON u.id = csr.student_user_id
WHERE csr.coach_user_id = :coach_id AND csr.status = 'active'
ORDER BY needs_response DESC, last_analysis_at DESC
LIMIT 100;
```

### 3.3 Redis 缓存策略

- key: `coach_dashboard:{coach_id}` TTL 30s
- 主动失效触发：
  - 学员上传新 swing_analysis → 失效 coach_id 的 list
  - 教练新增 annotation → 失效
  - 教练派发新 task → 失效
- 命中率目标 ≥80%（AC 隐性）

### 3.4 单学员详情看板

- 复用列表查询 + 加：近 7 天 issue trend、最近 5 份报告、教练对该学员的 annotation 时间线
- 缓存 key: `coach_dashboard:{coach_id}:{student_id}` TTL 30s

### 3.5 排序规则（FR-5）

```python
sort_key = (
    -int(needs_response),                # 待回应优先
    -days_since_last_contact,            # 长时间未联系次优
    -analyses_7d,                        # 活跃高
    -last_analysis_at.timestamp()
)
```

---

## 四、字段 v0.1

### 4.1 API 响应

```jsonc
{
  "students": [
    {
      "student_user_id": "...",
      "display_name": "张三", "avatar_url": "...",
      "analyses_7d": 4, "last_analysis_at": "...",
      "last_annotation_at": "...",
      "pending_tasks": 2,
      "needs_response": true
    }
  ],
  "total": 87,
  "cached_at": "..."
}
```

---

## 五、验证数据

- 压测 100 学员模拟数据 ≤2s P95（AC-1）
- 学员上传新分析 → 30s 内反映（AC-2）
- "待回应"指标准确：教练未回应批注 OR 学员 <24h 新报告（AC-3）

---

## 六、W26-W30 周计划

| 周 | 任务 |
| --- | --- |
| W26 | 聚合 SQL 评审 + index 检查 |
| W27 | service + API + Redis 缓存 |
| W28 | 教练 UI 列表 + 详情 |
| W29 | 性能压测 + 主动失效 hook |
| W30 | 灰度 + AC 验收 |

---

## 七、责任 / 风险 / 验收

### 责任

| 角色 | 责任 |
| --- | --- |
| 后端 | 聚合 + 缓存 |
| 客户端 | 列表 + 详情 UI |
| QA | 100 学员压测 |

### 风险

| ID | 风险 | 兜底 |
| --- | --- | --- |
| R-01 | 聚合 SQL >2s | 改 LEFT JOIN + 分步缓存 |
| R-02 | 缓存失效风暴 | 失效 + jitter；TTL ≥30s |
| R-03 | 教练有 200+ 学员 | 限 100；超出分页 |
| R-04 | "待回应"误判 | 单测 ≥10 case |

### AC

- [ ] AC-1 100 学员 ≤2s P95
- [ ] AC-2 状态变更 30s 反映
- [ ] AC-3 "待回应"准确

---

## 八、附录

| 任务 | 关系 |
| --- | --- |
| P2-M8-03 师生关系 | 数据源 |
| P2-M8-04 / 05 | 看板消费 annotation / task |
| P2-M8-07 教学报告 | 学员选源 |

---

## 九、变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-05-25 | 初版 |
