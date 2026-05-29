# P2-M13-07 · 互评 + 信用积分（meetup_feedbacks）· 启动包（W32 起跑）

> 版本：v0.1（2026-05-25）
> 上游真源：[`docs/23 §9.7`](../23-二期可编码规格说明书.md#97-p2-m13-07--互评--信用积分meetup_feedbacks)
> 前置：P2-M13-04 邀请 + P2-M13-06 风控

---

## 一、文档目的与边界

为 **P2-M13-07** 落地 W32-W35 后端 + 客户端 SOP，约球完成 24h 双方互评 + 信用分实时更新。

### 边界（不做）

- 不实现公开评价（仅 24h 后双方可见）
- 不修改 docs/22/23 字段

---

## 二、现状盘点

- M13-01 meetup_feedbacks 表已就位
- M13-06 信用积分计算已就位
- 约球完成事件需 M13-04 invitation 状态扩

### 缺口

5 个 FR 全部新增。

---

## 三、模块设计

### 3.1 新增

| 模块 | 路径 | 工程量 |
| --- | --- | --- |
| Service | `services/meetup_feedback_service.py` | 0.7 PW |
| API | POST/GET feedbacks | 0.3 PW |
| 24h 隔离 | service 层 + UI gate | 0.3 PW |
| UI | `pages/meetup/feedback/[invitation_id].tsx` | 0.5 PW |
| 信用分 hook | M13-06 联动 | 0.2 PW |

**合计：~2 PW**

### 3.2 互评流程

```
约球结束（用户标记 completed）→ T+24h 弹评价
  双方各自评：rating 1-5 + tags[] + comment?
  唯一约束：(invitation_id, user_id) 一次
  T+48h 双方互看对方评分（24h 隔离规则）
```

### 3.3 标签

| 标签 | 影响信用 |
| --- | --- |
| 守时 | +2 |
| 友好 | +1 |
| 教学耐心 | +2 |
| 失约 | -10 |
| 言语不当 | -15 + 风控告警 |

### 3.4 唯一约束

```sql
ALTER TABLE meetup_feedbacks ADD CONSTRAINT uq_feedback UNIQUE(invitation_id, rater_user_id);
```

---

## 四、字段 v0.1

```
POST /v1/meetup/feedbacks Body: { invitation_id, rating, tags, comment? }
GET  /v1/meetup/feedbacks/me
GET  /v1/meetup/feedbacks?invitation_id={id}  → 24h 后才返双方
```

---

## 五、验证数据

- 唯一约束（AC-1）
- 信用分阈值低不可发起（AC-2）
- 24h 隔离（AC-3）

---

## 六、W32-W35 周计划

| 周 | 任务 |
| --- | --- |
| W32 | service + API |
| W33 | UI + 唯一约束 |
| W34 | 信用分 hook |
| W35 | 灰度 + AC |

---

## 七、责任 / 风险 / 验收

### 责任

| 角色 | 责任 |
| --- | --- |
| 后端 | service / 信用 |
| 客户端 | UI |

### 风险

| ID | 风险 | 兜底 |
| --- | --- | --- |
| R-01 | 用户不评 | T+72h 提醒 1 次；不评不扣信用 |
| R-02 | 恶意评分 | 风控告警 + 人工 |
| R-03 | 24h 隔离被绕过 | service 层强制 |

### AC

- [ ] AC-1 唯一约束
- [ ] AC-2 阈值低不可发起
- [ ] AC-3 24h 隔离

---

## 八、附录

| 任务 | 关系 |
| --- | --- |
| P2-M13-04 邀请 | invitation_id |
| P2-M13-06 风控 | 信用源 |

---

## 九、变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-05-25 | 初版 |
