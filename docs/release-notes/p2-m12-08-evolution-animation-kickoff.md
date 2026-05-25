# P2-M12-08 · 追平演化动画（best-effort）· 启动包（W34 起跑）

> 版本：v0.1（2026-05-25）
> 上游真源：[`docs/23 §8.8`](../23-二期可编码规格说明书.md#88-p2-m12-08--追平演化动画best-effort)
> 前置：P2-M12-05 雷达 + M7-08 新特征

---

## 一、文档目的与边界

为 **P2-M12-08** 落地 W34-W37 客户端 + 设计 SOP，提供"逐步缩小差距，挥杆会进化成什么样"骨骼动画（best-effort）。

### 边界（不做）

- 不实现真实视频合成
- 不修改 docs/22/23 字段
- best-effort：失败静默降级雷达图渐变

---

## 二、现状盘点

- M12-04 输出 dimension_gaps
- 一期 Taro animation 可用
- 无骨骼线动画基础设施

### 缺口

6 个 FR 全部新增。

---

## 三、模块设计

### 3.1 新增

| 模块 | 路径 | 工程量 |
| --- | --- | --- |
| 插值算法 | `utils/posInterpolate.ts`（新） | 0.7 PW |
| 骨骼线动画 | `components/SkeletonAnimation.tsx`（新） | 1.2 PW |
| 三态切换 | `pages/pros/compare/...` 扩 | 0.5 PW |
| 雷达图渐变降级 | `components/RadarChart.tsx` 加 animate prop | 0.3 PW |
| 单测 | tests | 0.3 PW |

**合计：~3 PW**

### 3.2 插值算法

```typescript
function interpolatePose(userPose, proPose, t: number) {
  return userPose.map((kp, i) => ({
    x: kp.x + (proPose[i].x - kp.x) * t,
    y: kp.y + (proPose[i].y - kp.y) * t,
  }))
}
// t: 0=用户, 1=球手, 0.5=中间态
```

### 3.3 三态切换

```tsx
<SkeletonAnimation 
  start={userPose} 
  end={proPose}
  duration={3000}
  onPause={() => showLabel('中间态')}
/>
```

### 3.4 ≥3 个示例场景

- early_extension → 修复后骨骼线变化
- chicken_wing → 左肘改善
- reverse_spine → 脊柱回正

### 3.5 best-effort 降级

```typescript
if (!proPose || error) {
  return <RadarChart animate={true} from={userScores} to={proScores} />
}
```

---

## 四、字段 v0.1

无新 API；纯前端渲染消费 features_snapshot.pose。

---

## 五、验证数据

- ≥3 场景可用（AC-1）
- 失败静默降级（AC-2）

---

## 六、W34-W37 周计划

| 周 | 任务 |
| --- | --- |
| W34 | 插值 + 骨骼线骨架 |
| W35 | 三态切换 |
| W36 | 3 示例场景验证 |
| W37 | 降级 + 灰度 |

---

## 七、责任 / 风险 / 验收

### 责任

| 角色 | 责任 |
| --- | --- |
| 客户端 | UI |
| 设计 | 动画走查 |

### 风险

| ID | 风险 | 兜底 |
| --- | --- | --- |
| R-01 | 动画失真 | 仅 3 关键帧 + tween；不强求逐帧 |
| R-02 | RN 兼容 | adapters 分叉 |
| R-03 | 用户误以为是 AI 预测 | 文案"示意" |

### AC

- [ ] AC-1 ≥3 场景
- [ ] AC-2 静默降级

---

## 八、附录

| 任务 | 关系 |
| --- | --- |
| P2-M12-05 | 雷达基础 |
| P2-M7-08 | 特征源 |

---

## 九、变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-05-25 | 初版 |
