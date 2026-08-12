# P2-M11-03 · 学习路径 UI（首页"你在第 N 阶"+ 进度条）· 启动包（W28 起跑）

> 版本：v0.1（2026-05-25）
> 上游真源：[`docs/23 §7.3`](../23-二期可编码规格说明书.md#73-p2-m11-03--学习路径-ui首页你在第-n-阶-进度条)
> 前置：[`p2-m11-01-courses-schema-kickoff.md`](./p2-m11-01-courses-schema-kickoff.md) + M11-02 内容部分

---

## 一、文档目的与边界

为 **P2-M11-03** 落地 W28-W32 客户端 + 后端 SOP，让首页"学习路径"卡片驱动用户完成 7 阶段课程。

### 边界（不做）

- 不实现考核流程（M11-04）
- 不实现证书（M11-05）
- 不破坏一期首页既有"分析报告 / 训练计划"卡片排序（仅插入）

---

## 二、现状盘点

```
client/src/pages/index/index.tsx
  → 一期首页：分析报告 + 训练计划 + 球友圈
  → 无"学习路径"模块
backend/app/services/  → 无课程进度聚合
```

### 缺口（vs docs/23 §7.3 FR）

5 个 FR 全部新增。

---

## 三、模块设计

### 3.1 新增

| 模块 | 路径 | 工程量 |
| --- | --- | --- |
| 首页 LearningCard | `pages/index/components/LearningCard.tsx`（新） | 0.5 PW |
| 学习子页 | `pages/learning/index.tsx`（新） | 1 PW |
| 7 阶段树状视图 | `pages/learning/components/StageTree.tsx`（新） | 0.7 PW |
| Lesson 详情页 | `pages/learning/lesson/[id].tsx`（新） | 0.5 PW |
| 后端聚合 | `services/course_progress_service.py` | 0.5 PW |
| API | GET /v1/users/me/course-progress 等 4 个 | 0.5 PW |
| 单测 | tests | 0.3 PW |

**合计：~4 PW**

### 3.2 首页 LearningCard 卡片

```tsx
<Card
  title="📚 学习路径"
  subtitle="你在第 2 阶 · 全挥杆基础"
  progress={60}
  cta="继续学习"
  onTap={() => Taro.navigateTo({ url: '/pages/learning/index' })}
/>
```

插入位置：首页第 2 张卡片（分析报告下方）。一期分析报告 / 训练计划 / 球友圈位置不动。

### 3.3 学习子页路由

- 入口：训练 tab > "课程"二级子页（与"训练计划"并列）
- 7 阶段树状：
  ```
  第 1 阶 · 入门（5 节）✓ 已通关
  第 2 阶 · 全挥杆基础（7 节）● 进行中 60%
  第 3 阶 · 全挥杆进阶（6 节）○ 未解锁
  ...
  ```

### 3.4 聚合 API

```
GET /v1/users/me/course-progress
Response: {
  "current_stage": 2,
  "current_stage_progress": 0.6,
  "current_course_id": "...",
  "next_lesson_id": "...",
  "stages": [
    { "stage": 1, "status": "passed", "lesson_count": 5, "passed_count": 5 },
    { "stage": 2, "status": "in_progress", "lesson_count": 7, "passed_count": 4 },
    ...
  ]
}
```

后端 SQL：GROUP BY courses.stage + COUNT user_course_progress 状态。

### 3.5 进度刷新

- 首页激活时调一次 / cache 30s（避免高频）
- 考核完成 + 升阶 → 主动失效缓存

---

## 四、字段 v0.1

复用 M11-01 schema；无新表。

### 4.1 配置

```typescript
PHASE2_COURSES_ENABLED: boolean = false
```

---

## 五、验证数据

- 7 阶段假数据：UI 一目了然显示（AC-1/2）
- 一键跳转下一节未完成 lesson（AC-3）

---

## 六、W28-W32 周计划

| 周 | 任务 |
| --- | --- |
| W28 | LearningCard + 后端聚合 |
| W29 | StageTree 子页 |
| W30 | Lesson 详情页 |
| W31 | 缓存 + 失效 + 单测 |
| W32 | 灰度 + AC 验收 |

---

## 七、责任 / 风险 / 验收

### 责任

| 角色 | 责任 |
| --- | --- |
| 客户端 | 卡片 + 子页 |
| 后端 | 聚合 API |
| 设计 | 视觉走查 |

### 风险

| ID | 风险 | 兜底 |
| --- | --- | --- |
| R-01 | M11-02 内容延期 | 首批 5 节即可上线；UI 不阻塞 |
| R-02 | 首页加卡片破坏 UX | 设计走查 + AB 灰度 |
| R-03 | 阶段未解锁交互不清 | tooltip "完成前一阶段再解锁" |

### AC

- [ ] AC-1 首页卡片
- [ ] AC-2 7 阶段进度
- [ ] AC-3 跳下一节

---

## 八、附录

| 任务 | 关系 |
| --- | --- |
| P2-M11-01 schema | 消费 courses/lessons/user_course_progress |
| P2-M11-02 内容 | 首批 lesson |
| P2-M11-04 考核 | 升阶触发刷新 |
| P2-M11-05 证书 | 阶段通关推送 |

---

## 九、变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-05-25 | 初版 |
