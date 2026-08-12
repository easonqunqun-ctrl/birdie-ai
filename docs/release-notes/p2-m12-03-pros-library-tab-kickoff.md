# P2-M12-03 · 资源库 tab（独立浏览 + 标签筛选）· 启动包（W26 起跑）

> 版本：v0.1（2026-05-25）
> 上游真源：[`docs/23 §8.3`](../23-二期可编码规格说明书.md#83-p2-m12-03--资源库-tab独立浏览--标签筛选)
> 前置：P2-M12-02 首批球手入库

---

## 一、文档目的与边界

为 **P2-M12-03** 落地 W26-W31 客户端 + 后端 SOP，提供职业球手资源库的独立浏览体验（不依赖分析）。

### 边界（不做）

- 不修改 docs/22/23 字段
- 不新增 tab（独立子页）
- 不实现匹配算法（M12-04）

---

## 二、现状盘点

- M12-01 已建 6 张表；M12-02 已落首批 10-20 位球手
- 一期无任何"球手浏览"入口
- 一期 SwiperBanner / Card / Tabs 组件可复用

### 缺口

5 个 FR 全部新增。

---

## 三、模块设计

### 3.1 新增

| 模块 | 路径 | 工程量 |
| --- | --- | --- |
| API | GET /v1/pros/players + filter | 0.7 PW |
| 球手列表 | `pages/pros/players/index.tsx` | 1 PW |
| 球手详情 | `pages/pros/players/[id].tsx` | 0.7 PW |
| Clip 详情 | `pages/pros/clips/[id].tsx` | 0.8 PW |
| 标签筛选组件 | `components/ProsFilter.tsx` | 0.5 PW |
| 入口 banner / 教练对话 banner | 0.3 PW |
| 单测 | tests | 0.5 PW |
| Buffer | — | 0.5 PW |

**合计：~5 PW**

### 3.2 标签筛选

- gender: 男 / 女
- height_range: <175 / 175-185 / >185
- nationality: 国家代码
- style_tag: aggressive / balanced / smooth

### 3.3 入口

- 教练对话上方 banner "今日精选：Scottie Scheffler"（链 M12-06）
- 我的→职业球手库

### 3.4 视频加载策略

- 列表只加载 thumbnail
- 单 clip 详情懒加载 normalized_video_url
- skeleton overlay 用 canvas

---

## 四、字段 v0.1

```
GET /v1/pros/players?gender=&style_tag=&page=
GET /v1/pros/players/{id}
GET /v1/pros/clips/{clip_id}
```

---

## 五、验证数据

- 独立浏览（无需上传分析）（AC-1）
- 组合筛选不卡顿（AC-2）
- 单 clip 详情含 features_snapshot（AC-3）

---

## 六、W26-W31 周计划

| 周 | 任务 |
| --- | --- |
| W26 | API + 球手列表 |
| W27 | 球手详情 |
| W28 | Clip 详情 + skeleton overlay |
| W29 | 筛选 + 入口 |
| W30 | 单测 + 灰度 |
| W31 | AC 验收 |

---

## 七、责任 / 风险 / 验收

### 责任

| 角色 | 责任 |
| --- | --- |
| 客户端 | UI |
| 后端 | API + 缓存 |
| 设计 | 视觉走查 |

### 风险

| ID | 风险 | 兜底 |
| --- | --- | --- |
| R-01 | 视频加载慢 | thumbnail-only + 渐进式 |
| R-02 | 筛选条件过多卡顿 | DB index + 缓存 |
| R-03 | 单 clip URL 失效 | 24h 签名重生 |
| R-04 | 用户找不到入口 | 训练 tab 二级入口 + 教练 banner |

### AC

- [ ] AC-1 独立浏览
- [ ] AC-2 筛选可用
- [ ] AC-3 详情含 features_snapshot

---

## 八、附录

| 任务 | 关系 |
| --- | --- |
| P2-M12-01/02 schema + 内容 |
| P2-M12-04 匹配 | 详情页跳对比 |
| P2-M12-06 精选 banner | 入口 |

---

## 九、变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-05-25 | 初版 |
