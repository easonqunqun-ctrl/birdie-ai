# P2-M13-08 · 自助小型挑战赛模板（≥3 种）· 启动包（W34 起跑）

> 版本：v0.1（2026-05-25）
> 上游真源：[`docs/23 §9.8`](../23-二期可编码规格说明书.md#98-p2-m13-08--自助小型挑战赛模板推杆赛--距离赛--综合分赛-3-种)
> 前置：P2-M11-05 徽章框架 + 红线 R6

---

## 一、文档目的与边界

为 **P2-M13-08** 落地 W34-W37 后端 + 客户端 SOP，3 种 rule_template + 报名 + 上传成绩 + 完赛徽章。**严禁现金/实物奖励**（红线 R6，防变相博彩）。

### 边界（不做）

- **绝对**不引入现金/实物奖励
- 不修改 docs/22/23/06 字段
- 不实现高级排名 / 战队

---

## 二、现状盘点

- M13-01 self_organized_events + event_participations 表已就位
- M11-05 金色徽章框架已就位
- 一期成绩单图无审核流程

### 缺口

6 个 FR 全部新增。

---

## 三、模块设计

### 3.1 新增

| 模块 | 路径 | 工程量 |
| --- | --- | --- |
| Service | `services/event_service.py` | 1 PW |
| API | 4 个 events 接口 | 0.5 PW |
| 3 rule_template | `services/event_rules/{putting,distance,overall}.py` | 0.7 PW |
| 客户端 | `pages/meetup/events/*` | 0.5 PW |
| 完赛徽章 hook | 联动 M11-05 | 0.3 PW |

**合计：~3 PW**

### 3.2 3 种 rule_template

| 模板 | 规则 | 成绩单 |
| --- | --- | --- |
| putting_contest | 推杆 10 球决胜 | 杯口数 / 距离 |
| distance_contest | 距离赛 5 球决胜 | 最大距离 |
| overall_score | 综合分 18 洞 | 总杆数 |

### 3.3 报名

```
POST /v1/meetup/events/{id}/join
  → INSERT event_participations
  → max_participants 默认 8（超限 42910）
```

### 3.4 提交成绩

```
POST /v1/meetup/events/{id}/submit-score
  Body: { self_reported_score, score_image_url }
  → 走 M8-08 审核（成绩单图）
  → 审核通过 → 进入排行
```

### 3.5 完赛徽章

```python
def award_event_badge(event_id, user_id):
    badge = CourseCertificate(  # 复用 M11-05 表
        user_id=user_id,
        scope='meetup_event',
        event_id=event_id,
        title=f'{event.title} · 完赛',
        image_url=generate_badge_image(...)
    )
    # 绝不写 reward_cash / reward_item
```

法务双签确认无任何金钱/实物条款。

---

## 四、字段 v0.1

```
POST /v1/meetup/events
POST /v1/meetup/events/{id}/join
POST /v1/meetup/events/{id}/submit-score
GET  /v1/meetup/events?page=
```

---

## 五、验证数据

- 3 模板可用（AC-1）
- 法务双签无现金/实物（AC-2）
- 完赛徽章颁发（AC-3）

---

## 六、W34-W37 周计划

| 周 | 任务 |
| --- | --- |
| W34 | service + API |
| W35 | 3 模板 + 客户端 |
| W36 | 成绩审核 + 徽章 hook |
| W37 | 法务签字 + AC |

---

## 七、责任 / 风险 / 验收

### 责任

| 角色 | 责任 |
| --- | --- |
| 后端 | service / rules |
| 客户端 | UI |
| 法务 | 红线 R6 双签 |

### 风险

| ID | 风险 | 兜底 |
| --- | --- | --- |
| R-01 | 用户自发现金赌注 | 服务协议禁止 + 风控告警 |
| R-02 | 成绩单图造假 | M8-08 审核 + 用户标记 |
| R-03 | 8 人上限不够 | 后续可配；MVP 简单 |
| R-04 | 徽章被混同奖品 | 文案明确"荣誉" |

### AC

- [ ] AC-1 ≥3 模板
- [ ] AC-2 无现金/实物（双签）
- [ ] AC-3 徽章颁发

---

## 八、附录

| 任务 | 关系 |
| --- | --- |
| P2-M13-01 schema | events 表 |
| P2-M11-05 徽章 | 框架 |
| 红线 R6 | 合规 |

---

## 九、变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-05-25 | 初版 |
