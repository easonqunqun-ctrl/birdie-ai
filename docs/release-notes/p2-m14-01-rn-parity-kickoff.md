# P2-M14-01 · M7-M13 所有新模块在 RN 上 1:1 验证 · 启动包（W30 起跑）

> 版本：v0.1（2026-05-25）
> 上游真源：[`docs/23 §10.1`](../23-二期可编码规格说明书.md#101-p2-m14-01--m7-m13-所有新模块在-rn-上-11-验证)
> 前置：M7-M13 全部已合并

---

## 一、文档目的与边界

为 **P2-M14-01** 落地 W30-W37 RN 适配 + 验收 SOP，确保所有 M7-M13 模块在 RN 端能 1:1 编译 + 真机跑通，把一期 Taro RN bundle 门禁的端无关基础真正转化为可独立分发的 App。

### 边界（不做）

- 不修改 docs/22/23/06 字段
- 不重做信息架构（与小程序 1:1）
- 不在此处做 IAP / 上架（→ M14-02/03/04）

---

## 二、现状盘点

- 一期已有 `client/rn-shell`（taro-native-shell） + `make client-check-rn` bundle 门禁
- 一期已有 `src/adapters/*.{weapp,rn}.ts` 分叉机制（AGENTS.md §4）
- 一期 services / utils / store 已端无关（Jest 覆盖）
- 二期 27 个新增 kickoff（M7~M13）尚未 RN 实测

### 缺口

- 每个新模块均需补 `.rn.tsx` 端分叉文件 + adapters
- 微信生态依赖（订阅消息 / `wx.getLocation`）需 RN fallback（App push / 系统定位）
- RN bundle 大小 / 启动时间 / 首屏均无基线

---

## 三、模块设计

### 3.1 改造分类

| 模块 | RN 工作量 |
| --- | --- |
| M7 V2 引擎 | 0.5 PW（UI 端，新指标 / 雷达图等组件 .rn.tsx） |
| M8 教练工作台 | 1 PW（语音 / 涂鸦 / PDF 下载） |
| M9 画像 2.0 | 0.5 PW |
| M10 短杆 / 推杆 | 0.5 PW |
| M11 课程 | 1 PW（视频播放器 .rn.tsx） |
| M12 球手库 | 1.5 PW（并排视频 .rn.tsx + 雷达图） |
| M13 约球 | 1.5 PW（地图 / 定位 / 一次性二维码 RN fallback） |
| 公共 | 1.5 PW（push / 定位 / 分享） |

**合计：~8 PW**

### 3.2 微信生态依赖 → RN fallback

| 微信 API | RN fallback |
| --- | --- |
| 订阅消息 | App push（FCM / 极光 / 厂商通道） |
| `wx.getLocation` | `react-native-geolocation` |
| `wx.scanCode` | `react-native-camera` |
| 微信群一次性二维码（M13-04） | App 内分享 → 微信 / WhatsApp 等 |
| 微信支付 | M14-04 决策：跳转小程序 |

### 3.3 RN bundle 门禁强化

- 所有 PR 必须 `make client-check-rn` 绿；CI workflow `client-rn-check.yml` 已就位
- 增加 bundle 大小 lint（>80MB 报警）
- 增加冷启动 perf 基线（iPhone 12 + 小米 11）

---

## 四、字段 v0.1

- 无新字段；复用一期 + 二期全部接口与数据模型
- 仅 client 侧 adapters 新增：`src/adapters/{push,location,share,scan}.rn.ts`

---

## 五、验证数据

- `make client-check-rn` 全量通过（AC-1）
- RN 与小程序功能差异表 = 0（除微信生态）（AC-2）
- 真机 smoke：iPhone + 安卓各跑 `experience-version-smoke-runbook.md` 全量（AC-3）
- 启动 ≤2s / 主页面首屏 ≤1.5s（AC-4）

---

## 六、W30-W37 周计划

| 周 | 任务 |
| --- | --- |
| W30 | RN 适配优先级评估 + adapters 骨架 |
| W31 | M7 + M9 端分叉 |
| W32 | M8 + M11 端分叉（教练工作台 / 视频） |
| W33 | M10 + M12 端分叉（短杆 / 球手库） |
| W34 | M13 端分叉（约球 / 地图） |
| W35 | bundle perf 调优 + 启动时间 |
| W36 | iPhone + 安卓真机 smoke 全量 |
| W37 | AC 验收 + 交付给 M14-02/03 |

---

## 七、责任 / 风险 / 验收

### 责任

| 角色 | 责任 |
| --- | --- |
| RN 工程主 | 适配统筹 + bundle 门禁 |
| 各模块 owner | 协助 RN 端分叉评审 |
| QA | 真机 smoke |
| 性能小组 | 启动 / 首屏基线 |

### 风险

| ID | 风险 | 兜底 |
| --- | --- | --- |
| R-01 | 27 模块工作量爆 | 优先级评估 + 推后边缘模块（如 M12-08 进化动画） |
| R-02 | RN 端分叉踩坑 | 端无关层先 Jest 通过；分叉层走真机 |
| R-03 | 微信群二维码 fallback 影响 M13 体验 | App 内分享 + 文案说明 |
| R-04 | bundle 超 80MB | code split + 静态资源延迟下载 |
| R-05 | 视频组件 RN 差异 | 优先 react-native-video + 厂商兜底 |

### AC

- [ ] AC-1 make client-check-rn 全量通过
- [ ] AC-2 差异表 = 0（除微信生态）
- [ ] AC-3 真机 smoke 通过
- [ ] AC-4 perf 达标

---

## 八、附录

| 任务 | 关系 |
| --- | --- |
| M7-M13 全部 | 前置 |
| AGENTS.md §4 | 跨端守则 |
| experience-version-smoke-runbook | 验收脚本 |

---

## 九、变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-05-25 | 初版 |
