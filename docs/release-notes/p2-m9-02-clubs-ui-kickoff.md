# P2-M9-02 · 装备清单 UI · 启动包（W20 起跑）

> 版本：v0.1（2026-05-25）
> 状态：启动输入稿
> 适用范围：二期 Phase 2.1 期间，落地"我的→装备"Tab 完整 CRUD + 14 支上限 + 拍摄页联动
> 上游真源（待 PR #20 合并后生效）：[`docs/23 §5.2 · P2-M9-02`](../23-二期可编码规格说明书.md#52-p2-m9-02--装备清单-ui最多-14-支--自评-yardage)
> 前置 kickoff：[`p2-m9-01-user-profiles-v2-kickoff.md`](./p2-m9-01-user-profiles-v2-kickoff.md)（**硬依赖**：`user_clubs` 表已就绪）

---

## 一、文档目的与边界

### 1.1 目的

为 **P2-M9-02 装备清单 UI**落地一份「**W20 即可起跑（M9-01 W19 完成）、W22 装备 Tab 上线**」的客户端 + 后端 SOP：

- 一期 profile 页 + 拍摄页对"球杆"的处理现状
- 装备 Tab 完整 CRUD UI + 14 支上限校验
- 拍摄页 `params.tsx` 球杆默认值从装备清单取（UX 联动 FR-5）
- 与 M10-03 yardage book 数据复用约定

### 1.2 边界（**不**做项）

| 不做 | 原因 |
| --- | --- |
| 不修改 [`docs/22`](../22-二期开发迭代计划.md) / [`docs/23`](../23-二期可编码规格说明书.md) / [`docs/02`](../02-API接口设计文档.md) 字段 | 避免与 #18 / #19 / #20 race |
| 不动 `user_clubs` 表 schema | 由 M9-01 负责（已就位） |
| 不实现 M7-05 球杆标尺联动 | M7-05 直接读 `swing_analyses.club_type`，不依赖 `user_clubs` |
| 不实现 yardage book 完整 UI | M10-03 负责 |
| 不引入第三方球杆数据库（如 PING / TaylorMade 型号） | MVP 期 brand/model 自由文本 |

---

## 二、现状盘点

### 2.1 一期 profile 页

```
client/src/pages/profile/index.tsx
  ├─ 头像 / 昵称 / 编辑档案
  ├─ 会员信息
  ├─ 我的分析 / 训练
  ├─ 设置 / 反馈 / 关于
  └─ ❌ 没有"我的装备"入口
```

### 2.2 一期拍摄页 `params.tsx`

```
client/src/pages/analysis/params.tsx L78
  → useState<ClubType>('iron_7')   // 默认硬编码 7 号铁
client/src/pages/analysis/params.tsx L358-375
  → CLUB_TYPE_GROUPS 全 22 种球杆 ScrollView
```

**结论**：用户每次拍摄都从 22 种里选；如果常用 Driver / 9 号铁两支，每次都得手动选，效率低。M9-02 上线后默认从用户装备清单取首选。

### 2.3 已知缺口（vs docs/23 §5.2 FR）

| FR | 现状 | 缺口 |
| --- | --- | --- |
| FR-1 profile 页"我的装备"入口 | ❌ 无 | profile/index.tsx 加卡片 |
| FR-2 增删改 + brand/model/loft/avg_yards/std_yards/sort_order | ❌ 无 | 完整 CRUD 页面 |
| FR-3 14 支上限 | ❌ 无 | 应用层校验 + UI 提示 |
| FR-4 自评 yardage 可空 | ❌ 无 | M9-01 user_clubs.self_yardage_m 字段就位 |
| FR-5 拍摄页默认从装备清单取 | ❌ 硬编码 iron_7 | params.tsx 改造 |

---

## 三、模块设计

### 3.1 新增一览

| 模块 | 路径 | 职责 | 工程量 |
| --- | --- | --- | --- |
| 装备 Tab 入口 | `client/src/pages/profile/index.tsx` 改造 | "我的装备"卡片 | 0.5 PD |
| 装备列表页 | `client/src/pages/profile/clubs.tsx`（新） | 列表 + 14 支上限提示 | 1.5 PD |
| 装备编辑页 | `client/src/pages/profile/club-edit.tsx`（新） | 单支 CRUD | 1 PD |
| 拍摄页联动 | `client/src/pages/analysis/params.tsx` | 默认值从装备清单取 + 装备清单为空 fallback iron_7 | 0.5 PD |
| 后端 API | `backend/app/api/v1/users.py` 增 `/v1/users/me/clubs` | GET / POST / PUT / DELETE | 1.5 PD |
| Service | `backend/app/services/user_clubs_service.py`（新） | CRUD + 14 支校验 | 1 PD |
| 单测 | client jest + backend pytest | UI + 上限校验 + 联动 | 1 PD |

**合计：~7 PD**（与 docs/23 §5.2 估时 4 PW 略宽）

### 3.2 装备列表页 UI 草案

```
my-clubs.tsx
├─ 顶部统计：14 支已用 N，余 14-N
├─ 列表（按 sort_order）：
│   ├─ 球杆类型（icon）+ 自定义昵称（如"老搭子"）
│   ├─ 品牌 · 型号 · 杆面角度（可空显示"—"）
│   ├─ 自评码数（如"165m"，空显示"未填"）
│   └─ 右滑：编辑 / 删除
├─ 底部：[+ 添加球杆] 按钮（N=14 时禁用 + Toast"已达上限"）
```

### 3.3 装备编辑页 UI 草案

```
club-edit.tsx
├─ 球杆类型 dropdown（22 种 CLUB_TYPE_GROUPS）
├─ 自定义昵称 input（≤40 字）
├─ 品牌 + 型号 input（自由文本）
├─ 杆面角度 slider（loft：10° ~ 60°）
├─ 自评码数 input（米；0-400）
├─ 排序 / 启用开关
├─ [保存] / [删除]
```

### 3.4 拍摄页 `params.tsx` 联动（FR-5）

```tsx
const myClubs = await userClubsService.list({ is_active: true })
const defaultClubType = myClubs[0]?.club_type ?? 'iron_7'  // 装备清单首选；空 fallback iron_7

const [clubType, setClubType] = useState<ClubType>(defaultClubType)
```

> 如果用户没填装备清单（M9-02 未上线 / 装备清单为空），保持一期 `iron_7` fallback。

### 3.5 数据流

```
profile.tsx [我的装备] → clubs.tsx [列表] → club-edit.tsx [CRUD]
                                ↓
                          /v1/users/me/clubs
                                ↓
                          user_clubs 表（M9-01）
                                ↓
                          params.tsx 默认值消费
```

---

## 四、字段 / 配置草案 v0.1

### 4.1 API（与 docs/02 §11.3 对齐，本任务实现）

```
GET    /v1/users/me/clubs
POST   /v1/users/me/clubs           Body: { club_type, nickname, self_yardage_m, ... }
PUT    /v1/users/me/clubs/{id}      Body: { ... }
DELETE /v1/users/me/clubs/{id}
```

错误码：

- `40002`：参数校验失败（如 self_yardage_m > 400）
- `40020`：达到 14 支上限（自定义业务错误码）

### 4.2 配置项

```python
PHASE2_PROFILE_V2_ENABLED: bool = False  # 与 M9-01/03 共享 flag
```

---

## 五、验证数据

### 5.1 单测

- 客户端 jest：clubs.tsx 列表渲染 + 14 支禁用按钮
- 后端 pytest：service.add_club 第 15 支触发 `BadRequestError`

### 5.2 端到端验证

- 添加 5 支不同球杆 → 拍摄页默认选首选；删除全部后默认 iron_7

### 5.3 性能（NFR）

- 列表加载 14 支 < 800ms
- CRUD < 500ms

---

## 六、W20-W22 周计划

| 周 | 任务 | DoD |
| --- | --- | --- |
| **W20** | 本文件评审；UI 设计稿（列表 + 编辑 + 拍摄联动） | ☑ 设计稿走查通过 |
| **W21** | 后端 API + service + 14 支校验单测 | ☑ 4 个端点 smoke ；☑ 14 支上限单测 |
| **W22** | 客户端 clubs.tsx / club-edit.tsx 实现 + params.tsx 联动 + AC | ☑ AC-1/2/3 全勾 |

---

## 七、责任 / 风险 / 验收

### 7.1 责任

| 角色 | 责任 |
| --- | --- |
| 客户端 Lead | 总 owner；列表 / 编辑 / 拍摄联动 |
| 后端 | API + service + 14 支校验 |
| 设计 | 列表页空状态 + 14 支已达上限提示 |

### 7.2 风险

| ID | 风险 | 兜底 |
| --- | --- | --- |
| R-01 | 用户拍摄时装备清单为空 → 默认 iron_7 | 拍摄页加引导 banner"完善装备清单，AI 教练更懂你 →" |
| R-02 | 14 支用户全删后无装备状态 | 拍摄页 fallback 一期默认（iron_7） |
| R-03 | brand/model 自由文本拼写不一致影响 yardage book 统计 | MVP 期不做 normalize；M10-03 评估 |
| R-04 | DELETE 触发用户既有 swing_analyses 关联失效 | swing_analyses.club_type 是字符串字段，不引用 user_clubs.id；删 club 不影响历史报告 |

### 7.3 AC 兜底（复述 docs/23 §5.2）

- [ ] **AC-1**：profile 页装备 tab 可增删改
- [ ] **AC-2**：14 支上限校验生效
- [ ] **AC-3**：拍摄页"球杆类型"从装备清单取默认值

---

## 八、附录

### 8.1 与相邻 PLAN-ID 分工

| 任务 | 本任务交付 / 关系 |
| --- | --- |
| P2-M9-01 数据模型 | 消费 `user_clubs` 表 |
| P2-M9-03/04/05 | 共享 profile 编辑页 UI 风格 |
| P2-M10-03 yardage book | 复用 `user_clubs.self_yardage_m` 数据 |
| P2-M7-05 球杆标尺 | 不直接依赖；读 swing_analyses.club_type |

---

## 九、变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-05-25 | 初版；UI 设计 + 拍摄页联动 + 14 支上限 |
