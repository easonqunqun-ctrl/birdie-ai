# P2-M12-09 · 教练 M8 批注内引用职业球手参考素材 · 启动包（W28 起跑）

> 版本：v0.1（2026-05-25）
> 上游真源：[`docs/23 §8.9`](../23-二期可编码规格说明书.md#89-p2-m12-09--教练-m8-批注内引用职业球手参考素材)
> 前置：P2-M8-04 批注 + P2-M12-02 球手入库

---

## 一、文档目的与边界

为 **P2-M12-09** 落地 W28-W31 客户端 + 后端 SOP，让教练在 M8 批注里嵌入职业球手 clip 引用。

### 边界（不做）

- 不修改 docs/22/23 字段
- 不允许学员主动引用（只教练）

---

## 二、现状盘点

- M8-04 `analysis_annotations.annotation_type` 已含 'video_ref' + pro_clip_id
- M8-04 教练 4 入口已就绪
- M12-03 资源库已就位

### 缺口

4 个 FR 全部新增。

---

## 三、模块设计

### 3.1 改造

| 模块 | 路径 | 工程量 |
| --- | --- | --- |
| 教练批注 UI 加"引用 pro_clip" | `pages/coach/analysis-annotate/...` | 0.5 PW |
| Clip picker 弹窗 | `components/ProClipPicker.tsx`（新） | 0.5 PW |
| 学员侧批注卡片增强 | `pages/analysis/report.tsx` | 0.5 PW |
| API payload 扩 | M8-04 既有接口加 video_ref 字段 | 0.2 PW |
| 单测 | tests | 0.3 PW |

**合计：~2 PW**

### 3.2 教练 UX

```
[新批注] 4 入口 → 第 5 入口"引用球手 clip"
  → 弹 ProClipPicker（按球手 / 类目 / 关键字搜）
  → 选定 → 触发 POST /v1/coach/.../annotations { type: 'video_ref', pro_clip_id }
```

### 3.3 学员侧

```tsx
{annotation.annotation_type === 'video_ref' && (
  <ProClipReferenceCard 
    clip_id={annotation.pro_clip_id}
    onTap={() => navigateTo({ url: `/pages/pros/clips/${clip_id}` })}
    onCompare={() => navigateTo({ url: `/pages/pros/compare/...` })}
  />
)}
```

### 3.4 审核

视频引用本身无需 audit（pro_clip 已审过）；教练 coach_note 走 M8-08 文本审核。

---

## 四、字段 v0.1

复用 M8-04 既有 schema + pro_clip_id 字段。

---

## 五、验证数据

- 教练能插入 ≥1 个 pro_clip（AC-1）
- 学员可见缩略图（AC-2）
- 一键跳转资源库或对比（AC-3）

---

## 六、W28-W31 周计划

| 周 | 任务 |
| --- | --- |
| W28 | UI 集成 |
| W29 | ProClipPicker + 学员卡片 |
| W30 | 跳转链路 + 单测 |
| W31 | 灰度 + AC |

---

## 七、责任 / 风险 / 验收

### 责任

| 角色 | 责任 |
| --- | --- |
| 客户端 | UI |
| 后端 | payload 扩 |

### 风险

| ID | 风险 | 兜底 |
| --- | --- | --- |
| R-01 | clip 下架后学员侧显示空 | 后端返 40404；UI tip"已下架" |
| R-02 | 教练误引球手 | 弹搜索 + 标签 |
| R-03 | 跳转混乱 | 默认资源库；"看对比"按钮另设 |

### AC

- [ ] AC-1 教练可插入
- [ ] AC-2 学员缩略图
- [ ] AC-3 跳转链路

---

## 八、附录

| 任务 | 关系 |
| --- | --- |
| P2-M8-04 | 共用接口 |
| P2-M12-03 资源库 | picker 来源 |
| P2-M12-05 对比 | 跳转目标 |

---

## 九、变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-05-25 | 初版 |
