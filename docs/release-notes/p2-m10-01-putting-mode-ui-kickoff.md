# P2-M10-01 · 推杆模式 UI（拍摄页选模式 + 报告页专属维度）· 启动包（W21 起跑）

> 版本：v0.1（2026-05-25）
> 上游真源：[`docs/23 §6.1`](../23-二期可编码规格说明书.md#61-p2-m10-01--推杆模式-ui拍摄页选模式--报告页专属维度)
> 前置：[`p2-m7-11-...`]（待 PR）putting pipeline；P2-M7-14 灰度

---

## 一、文档目的与边界

为 **P2-M10-01** 落地 W21-W26 客户端 SOP，引入"推杆模式"全链路（拍摄页模式选择 → 引擎路由 → 报告专属维度）。

### 边界（不做）

- 不实现推杆 AI pipeline 本身（M7-11）
- 不实现切杆 UI（M10-02）
- 不修改一期 full_swing UI（不破坏既有 UX）

---

## 二、现状盘点

```
client/src/pages/analysis/params.tsx
  → 仅有 club_type / camera_angle 两参数；无 mode 字段
client/src/pages/analysis/report.tsx
  → 单一 4 阶段 + 6 issue 渲染；无 mode 分支
```

### 缺口

- 拍摄页：模式选择 UI
- 引擎调用：mode 参数
- 报告页：4 阶段 + 4 维度专属渲染（钟摆稳定 / 头部稳定 / 推杆面方正 / 节奏）
- 错误码 50123 处理

---

## 三、模块设计

### 3.1 新增 / 改造

| 模块 | 路径 | 工程量 |
| --- | --- | --- |
| ModeSelector 组件 | `components/ModeSelector.tsx`（新） | 0.5 PW |
| params.tsx 改造 | `pages/analysis/params.tsx` | 0.5 PW |
| API 调用加 mode | `services/analysisService.ts` | 0.3 PW |
| Putting Report 组件 | `pages/analysis/components/PuttingReport.tsx`（新） | 1.5 PW |
| report.tsx mode 分支 | `pages/analysis/report.tsx` | 0.5 PW |
| 错误码 UI 提示 | `constants/errorMessages.ts` 加 50123 | 0.2 PW |
| 单测 | `__tests__/PuttingReport.test.tsx` | 0.5 PW |

**合计：~4 PW**（与 docs/23 §6.1 持平）

### 3.2 ModeSelector 组件

```tsx
<ModeSelector
  value={mode}
  options={[
    { value: 'full_swing', label: '全挥杆', icon: '⛳' },
    { value: 'putting', label: '推杆', icon: '🎯' },
    { value: 'chipping', label: '切杆', icon: '🏌️', disabled: !chippingEnabled },
  ]}
  onChange={setMode}
/>
```

### 3.3 mode + club_type 联动校验

```tsx
useEffect(() => {
  if (mode === 'putting' && !['putter'].includes(clubType)) {
    Taro.showModal({ title: '提示', content: '推杆模式建议选 putter' })
  }
}, [mode, clubType])
```

后端 50123 错误返回时映射友好文案："推杆模式需选 putter 球杆"。

### 3.4 报告页专属维度

```tsx
{analysis.mode === 'putting' ? (
  <PuttingReport
    phases={analysis.phases}  // [setup, backswing, impact, follow]
    putting_features={analysis.putting_features}  // pendulum_stability / head_stability / face_alignment / tempo
  />
) : ...}
```

---

## 四、字段 v0.1

### 4.1 API

```
POST /v1/analyses
  Body: { ..., mode: 'putting' }  // 默认 'full_swing'
```

`analysis_mode` 已在 swing_analyses 表内（docs/03 §8.1，由 M7-11 同期落地）。

### 4.2 配置

```typescript
PHASE2_PUTTING_MODE_ENABLED: boolean = false  // 灰度开关，与 M7-11 共用
```

---

## 五、验证数据

- E2E：选 putting → 引擎返推杆 4 维度 → 报告展示（AC-1）
- 选 putting + driver → 报 50123 + 中文提示（AC-2）
- 4 大推杆维度可见且数值正确（AC-3）

---

## 六、W21-W26 周计划

| 周 | 任务 |
| --- | --- |
| W21 | ModeSelector + params 改造 |
| W22 | PuttingReport 组件骨架 |
| W23 | 与 M7-11 联调 mock |
| W24 | 错误码 + 灰度开关 |
| W25 | 灰度 10% 用户 + AC 验收 |
| W26 | 灰度 50% |

---

## 七、责任 / 风险 / 验收

### 责任

| 角色 | 责任 |
| --- | --- |
| 客户端 Lead | UI + 联调 |
| 算法 | M7-11 接口 |

### 风险

| ID | 风险 | 兜底 |
| --- | --- | --- |
| R-01 | M7-11 延期 | 客户端先 mock；不阻塞 UI |
| R-02 | 用户混淆 mode 与 club_type | 50123 友好文案 + 模式 tooltip |
| R-03 | 推杆视频拍摄需 face_on | UI 提示固定 face_on |

### AC

- [ ] AC-1 mode=putting 链路通
- [ ] AC-2 错配 50123 + 提示
- [ ] AC-3 4 维度可见

---

## 八、附录

| 任务 | 关系 |
| --- | --- |
| P2-M7-11 推杆 pipeline | 提供 putting_features |
| P2-M10-02 切杆 UI | 复用 ModeSelector |
| P2-M7-14 灰度 | engine_version 路由 |

---

## 九、变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-05-25 | 初版；ModeSelector + PuttingReport |
