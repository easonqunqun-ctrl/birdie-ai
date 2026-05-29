# P2-M8-02 · 教练身份切换 UI · 启动包（W22 起跑）

> 版本：v0.1（2026-05-25）
> 状态：启动输入稿
> 适用范围：二期 Phase 2.3 期间，落地"同 user_id 同时拥有 user/coach 双视图"切换 UI
> 上游真源（待 PR #20 合并后生效）：[`docs/23 §4.2 · P2-M8-02`](../23-二期可编码规格说明书.md#42-p2-m8-02--教练身份切换-ui同-user_id-profile-页入口)
> 前置 kickoff：[`p2-m8-01-coach-profile-verification-kickoff.md`](./p2-m8-01-coach-profile-verification-kickoff.md)（**硬依赖**：`coach_profiles.status='active'`）

---

## 一、文档目的与边界

### 1.1 目的

为 **P2-M8-02** 落地一份「**W22 起跑、W24 上线**」的客户端 + 后端 SOP，明确：

- 一期"我的"页面无角色切换；二期单 user_id 双视图
- 切换通过 `POST /v1/auth/role-switch` 重发短 JWT 或 header `X-Role: coach`（长 JWT）
- TabBar 文案 / 部分入口动态变更（**不**新增 tab，与 [`docs/22 §九`](../22-二期开发迭代计划.md) 一致性约束对齐）
- 非教练用户**不**显示切换入口

### 1.2 边界（**不**做项）

| 不做 | 原因 |
| --- | --- |
| 不修改 docs/22/23 字段 | 避免 race |
| 不新增 tab / 路由结构 | 一致性约束 |
| 不影响一期 user 体验（默认 user 视图） | 兼容 |
| 不实现学员绑定 | M8-03 负责 |

---

## 二、现状盘点

### 2.1 一期 JWT 设计

- backend 签发 JWT 含 `sub: user_id`，**无** role claim
- 客户端登录后默认拥有所有 `/v1/users/*` 接口权限
- 教练侧接口（M8-04~10 拟）走 `/v1/coach/*`，需要校验 coach role

### 2.2 已知缺口（vs docs/23 §4.2 FR）

| FR | 现状 | 缺口 |
| --- | --- | --- |
| FR-1 "我的"页面切换开关（仅 active 教练可见） | ❌ | profile/index.tsx 加 |
| FR-2 TabBar 文案 / 入口动态变更 | ❌ | tabbar 适配 |
| FR-3 `POST /v1/auth/role-switch` 或 `X-Role: coach` | ❌ | 后端选择 |
| FR-4 双视图共享 user_id | ✅ 一期 user_id | 不创建新账号 |

---

## 三、模块设计

### 3.1 新增一览

| 模块 | 路径 | 职责 | 工程量 |
| --- | --- | --- | --- |
| 后端 JWT 改造 | `backend/app/core/security.py` | role claim 或 X-Role header 解析 | 1 PD |
| Auth API | `POST /v1/auth/role-switch`（可选） | 切换后返新 JWT | 0.5 PD |
| coach 中间件 | `backend/app/api/middleware/coach.py`（新） | `/v1/coach/*` 校验 role | 0.5 PD |
| 客户端 store | `client/src/store/userStore.ts` | currentRole: 'user' \| 'coach' | 0.5 PD |
| profile 切换入口 | `client/src/pages/profile/index.tsx` 改造 | 仅 active 教练展示 | 0.5 PD |
| Tabbar 文案适配 | `client/src/app.config.ts` 或 runtime adapter | 切换后 tab 文案变更 | 1 PD |
| 单测 | jest + pytest | 入口可见性 + 校验 | 0.5 PD |

**合计：~4.5 PD**（与 docs/23 §4.2 估时 2 PW 偏宽）

### 3.2 JWT 设计选项

**方案 A：短 JWT 重发**（推荐）

- `POST /v1/auth/role-switch { role: 'coach' }` → 返回新 JWT，scope 含 coach
- 客户端切换后所有请求带新 JWT
- 优点：明确、易追溯；缺点：需要刷新 token

**方案 B：长 JWT + X-Role header**

- JWT 仍 user_id only；每请求附 `X-Role: coach`
- 后端中间件读 header → 查 `coach_profiles.status='active'` → 注入 role context
- 优点：实现简单；缺点：客户端容易遗漏 header；scope 不在 token 内

**W22 评审选 A**（更安全）。

### 3.3 切换入口可见性

```tsx
// client/src/pages/profile/index.tsx
const { user, currentRole, setRole } = useUserStore()
const isActiveCoach = user.coach_profile?.status === 'active'

{isActiveCoach && (
  <View className='profile__role-switch'>
    <Switch checked={currentRole === 'coach'} onChange={(v) => setRole(v ? 'coach' : 'user')} />
    <Text>{currentRole === 'coach' ? '当前为教练身份' : '切换为教练身份'}</Text>
  </View>
)}
```

### 3.4 TabBar 文案适配

| Tab | user 模式 | coach 模式 |
| --- | --- | --- |
| 首页 | 首页 | 工作台 |
| 训练 | 训练 | 学员 |
| 我的 | 我的 | 我的 |

> Taro 的 `Taro.setTabBarItem` 可动态改 text；切换 role 后调用即可（Cross-platform 验证：小程序支持，RN 需用 react-navigation API 等价方案）。

### 3.5 错误码

- `40310` 当前账号不是已审核教练（M8-01 已定义）
- `40320` 切换 role 失败（如 status != active）

---

## 四、字段 / 配置草案 v0.1

### 4.1 API

```
POST /v1/auth/role-switch
Body: { role: 'coach' | 'user' }
Response: { access_token: '...', role: 'coach', expires_in: 3600 }
```

### 4.2 配置项

```python
PHASE2_COACH_ENABLED: bool = False
```

---

## 五、验证数据

### 5.1 单测

- 后端：active 教练 → 切换成功；非教练 → 40310；status=rejected → 40320
- 客户端：profile 页 isActiveCoach=false → 切换开关不可见

### 5.2 端到端验证

- 教练 user_id 登录 → 切换 coach → 调用 `/v1/coach/students` 返回 200
- 切回 user → 调用 `/v1/coach/students` 返回 40310

---

## 六、W22-W24 周计划

| 周 | 任务 | DoD |
| --- | --- | --- |
| **W22** | 评审；JWT 方案选 A；客户端 store + UI 设计 | ☑ 评审通过 |
| **W23** | 后端 role-switch API + coach 中间件 | ☑ 端到端 smoke |
| **W24** | 客户端切换 UI + TabBar 适配（Taro 双端） | ☑ AC-1/2/3 全勾 |

---

## 七、责任 / 风险 / 验收

### 7.1 责任

| 角色 | 责任 |
| --- | --- |
| 后端 | JWT 改造 + 中间件 |
| 客户端 | profile 入口 + TabBar 适配 |
| 安全 | role-switch 接口安全审计 |

### 7.2 风险

| ID | 风险 | 兜底 |
| --- | --- | --- |
| R-01 | TabBar 文案适配 RN 不支持 | 用 React Navigation 等价 API；adapters/ 分叉 |
| R-02 | 用户切换后忘记切回 user，影响 user 接口 | currentRole 显式注入；user 接口不依赖 role |
| R-03 | JWT 过期与 role 切换交叉 | 每次切换返回完整 token；旧 token 加入 deny list（W23 评估） |
| R-04 | 教练注销账户后 status 变 rejected，但客户端缓存仍 coach | 启动时 fetchMe 强制刷新 role；接口侧 401 处理 |

### 7.3 AC 兜底（复述 docs/23 §4.2）

- [ ] **AC-1**：active 教练一键切换
- [ ] **AC-2**：非教练用户不见切换入口
- [ ] **AC-3**：切换后所有 `/v1/coach/*` 接口可用

---

## 八、附录

### 8.1 与相邻 PLAN-ID 分工

| 任务 | 关系 |
| --- | --- |
| P2-M8-01 资质审核 | 提供 coach_profiles.status |
| P2-M8-03 学员绑定 | 切到 coach 后才能管理学员 |
| P2-M8-04~10 | 业务功能依赖本任务 role 切换 |

---

## 九、变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-05-25 | 初版；JWT 方案 A + 切换 UI + TabBar 适配 |
