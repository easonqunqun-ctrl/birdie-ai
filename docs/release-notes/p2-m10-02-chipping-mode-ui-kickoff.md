# P2-M10-02 · 切杆模式 UI · 启动包（W22 起跑）

> 版本：v0.1（2026-05-25）
> 上游真源：[`docs/23 §6.2`](../23-二期可编码规格说明书.md#62-p2-m10-02--切杆模式-ui)
> 前置：[`p2-m10-01-putting-mode-ui-kickoff.md`](./p2-m10-01-putting-mode-ui-kickoff.md)（ModeSelector 复用） + M7-12 切杆 pipeline

---

## 一、文档目的与边界

为 **P2-M10-02** 落地 W22-W26 客户端 SOP，引入"切杆模式"全链路，复用 M10-01 的 ModeSelector + 报告组件。

### 边界（不做）

- 不实现切杆 AI pipeline 本身（M7-12）
- 不动 full_swing / putting 报告布局

---

## 二、现状盘点

依赖 M10-01 已落 ModeSelector / mode 路由。本任务仅扩 "chipping" 选项 + 3 维度报告。

### 缺口

- ModeSelector chipping 选项激活
- ChippingReport 组件
- 4 阶段 + 3 维度（半挥幅度 / 杆面打开 / 击球点）

---

## 三、模块设计

### 3.1 新增

| 模块 | 路径 | 工程量 |
| --- | --- | --- |
| ChippingReport 组件 | `pages/analysis/components/ChippingReport.tsx`（新） | 1.2 PW |
| ModeSelector chipping 启用 | `components/ModeSelector.tsx` flag | 0.2 PW |
| report.tsx 分支 | `pages/analysis/report.tsx` | 0.3 PW |
| 提示文案 | `constants/modeHints.ts` | 0.2 PW |
| 单测 | tests | 0.5 PW |
| 视觉 / Buffer | — | 0.6 PW |

**合计：~3 PW**（与 docs/23 §6.2 持平）

### 3.2 推荐 club_type 联动

```tsx
useEffect(() => {
  if (mode === 'chipping' && !['wedge', 'iron_8', 'iron_9'].includes(clubType)) {
    Taro.showToast({ title: '切杆建议选 wedge 或 iron_8/9', icon: 'none' })
  }
}, [mode, clubType])
```

### 3.3 ChippingReport 渲染

```tsx
<ChippingReport
  phases={analysis.phases}   // setup / backswing / impact / follow（半挥）
  chipping_features={analysis.chipping_features}  // half_swing_amplitude / face_open / contact_point
/>
```

---

## 四、字段 v0.1

复用 M10-01 + M7-12 接口；mode='chipping'。

```typescript
PHASE2_CHIPPING_MODE_ENABLED: boolean = false
```

---

## 五、验证数据

- E2E：mode=chipping 全链路通（AC-1）
- 3 维度可见（AC-2）

---

## 六、W22-W26 周计划

| 周 | 任务 |
| --- | --- |
| W22 | ChippingReport 组件 |
| W23 | ModeSelector + report.tsx 改造 |
| W24 | 与 M7-12 联调 mock |
| W25 | 灰度 10% |
| W26 | 灰度 50% |

---

## 七、责任 / 风险 / 验收

### 责任

| 角色 | 责任 |
| --- | --- |
| 客户端 | UI |
| 算法 | M7-12 接口 |

### 风险

| ID | 风险 | 兜底 |
| --- | --- | --- |
| R-01 | M7-12 延期 | mock |
| R-02 | 切杆视频拍摄角度复杂 | 提示固定 face_on |
| R-03 | 用户误用 driver 切杆 | toast 提示但不阻塞 |

### AC

- [ ] AC-1 mode=chipping 链路通
- [ ] AC-2 3 维度可见

---

## 八、附录

| 任务 | 关系 |
| --- | --- |
| P2-M10-01 | ModeSelector 复用 |
| P2-M7-12 | chipping pipeline |

---

## 九、变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-05-25 | 初版；ChippingReport |
