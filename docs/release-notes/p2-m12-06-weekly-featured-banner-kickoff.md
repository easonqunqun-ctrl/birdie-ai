# P2-M12-06 · 每周精选 banner + 4 周连续 publish · 启动包（W34 起跑）

> 版本：v0.1（2026-05-25）
> 上游真源：[`docs/23 §8.6`](../23-二期可编码规格说明书.md#86-p2-m12-06--每周精选-banner--4-周连续-publish)
> 前置：P2-M12-02 球手入库

---

## 一、文档目的与边界

为 **P2-M12-06** 落地 W34-W37 内容运营 + 客户端 SOP，首页 banner 每周轮换"职业精选 topic"。

### 边界（不做）

- 不修改 docs/22/23 字段
- 不破坏一期首页布局

---

## 二、现状盘点

- M12-01 已有 pro_topics 表（含 weekly_featured_at）
- 一期首页有 SwiperBanner（一期 ENG-11）
- 内容运营无现成 topic 模板

### 缺口

5 个 FR 全部新增。

---

## 三、模块设计

### 3.1 改造

| 模块 | 路径 | 工程量 |
| --- | --- | --- |
| API | GET /v1/pros/topics/featured | 0.3 PW |
| 首页 banner 组件 | `pages/index/index.tsx` 加 ProTopicBanner | 0.5 PW |
| Topic 详情页 | `pages/pros/topics/[id].tsx` | 0.5 PW |
| 内容运营 SOP | 4 周 topic 内容撰写 | 0.5 PW（运营） |
| 调度任务 | cron weekly_featured_at 失效 | 0.2 PW |

**合计：~2 PW**

### 3.2 4 周节奏 SOP

| 周 | 主题 |
| --- | --- |
| W1 | Scottie Scheffler 大师赛挥杆解析 |
| W2 | Rory McIlroy 推杆稳定性 |
| W3 | LPGA 球手切杆杆面控制 |
| W4 | 中国球手 X 短杆训练习惯 |

每周一上线，下周一自动失效（仍可在资源库 tab 找到）。

### 3.3 缓存策略

- key `pros:topic:weekly` TTL 60s
- 推送时主动失效

---

## 四、字段 v0.1

```
GET /v1/pros/topics/featured  → 当前 weekly_featured_at 在 ±7 天内的 topic
GET /v1/pros/topics/{id}
```

---

## 五、验证数据

- 首页 banner 加载 ≤500ms（NFR）
- 4 周连续上线（AC-2）
- 过期自动归档（AC-3）

---

## 六、W34-W37 周计划

| 周 | 任务 |
| --- | --- |
| W34 | API + banner |
| W35 | topic 详情 + cron |
| W36 | 内容运营 4 周编排 |
| W37 | AC 验收 |

---

## 七、责任 / 风险 / 验收

### 责任

| 角色 | 责任 |
| --- | --- |
| 内容运营 | topic 撰写 + 节奏 |
| 后端 | API + cron |
| 客户端 | banner |
| 设计 | 视觉 |

### 风险

| ID | 风险 | 兜底 |
| --- | --- | --- |
| R-01 | 内容延期 | 提前 4 周编排 |
| R-02 | banner 影响首页 UX | 设计走查 + AB |
| R-03 | 过期 banner 仍展示 | cron 失效 + 缓存清 |

### AC

- [ ] AC-1 banner 上线
- [ ] AC-2 4 周连续
- [ ] AC-3 过期自动归档

---

## 八、附录

| 任务 | 关系 |
| --- | --- |
| P2-M12-01/02 | topic + clip 源 |
| P2-M12-07 解说 | topic 内容来源 |

---

## 九、变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-05-25 | 初版 |
