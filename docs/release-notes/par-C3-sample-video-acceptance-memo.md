# par-C3 · 示例视频体验入口（docs/01 §3.6） · 验收纪要

> **关联**：`docs/19` **DOC-04 / Q-C1 / par-C3** · `docs/01` **§3.6 示例视频体验入口** · MVP M2「分析体验门面」
> **本纪要只覆盖 par-C3（示例视频）**；par-C1（账号注销） / par-C2（会员到期）见同目录另两份纪要。

---

## 0. 元信息

| 字段 | 值 |
|------|----|
| **纪要 ID** | `par-C3` · `sample-video-2026-05-21` |
| **关联 PLAN-ID** | `Q-C1` / `par-C3` / `DOC-04`（汇总） |
| **关联文档** | [`docs/01 §3.6`](../01-MVP功能需求规格说明书.md#36-示例视频体验入口) · [`docs/02 §3.7 GET /v1/analyses/sample`](../02-API接口设计文档.md) · [`docs/19 §6.3 DOC-04`](../19-产品开发迭代计划-当前队列.md#63-主表plan-id) |
| **代码版本** | `main @ HEAD`（W3 上线后 W7 收尾，2026-05-21 文档对齐） |
| **验收范围** | `docs/01 §3.6` 的 6 条产品要求 + 隐含项（不入库、不计配额、`id='sample'` 固定） |
| **验收日期** | 2026-05-21 |
| **起草** | 工程侧自动化纪要 |
| **复核（待签）** | 产品 ▢　工程 ▢ |

---

## 1. 验收依据

`docs/01 §3.6` 关键约束：

1. **入口位置**：首页底部 / 引导页底部 / 拍摄页底部「先看示例报告」
2. **跳过登录与上传**：新用户无需注册、无需配额、无需拍视频即可体验完整报告
3. **报告内容**：与真实分析一致的雷达图、骨骼叠加、阶段评分、Drill 推荐等
4. **明显标记**：报告页顶部标识「示例报告」
5. **CTA**：报告底部「开始我的分析」直接拉起拍摄/上传链路
6. **不污染数据**：示例报告不入库、不计配额、不影响"分析次数"统计

---

## 2. 实现总览

### 2.1 接口与代码路径

| 端点 / 文件 | 角色 |
|-------------|------|
| `GET /v1/analyses/sample` | 匿名可访问，返回固定示例 JSON，不入库 |
| `backend/app/api/v1/analyses.py` `get_sample_analysis` | FastAPI 路由（鉴权 `optional`，便于未来埋点） |
| `backend/app/services/sample_fixture.py` `build_sample_report()` | 构造一份固定示例报告（阶段评分、issue、drill、video / skeleton url） |
| `backend/app/models/analysis.py::SwingAnalysis.is_sample` | 真实库内若有"示例"性质记录则置 `True`，与用户记录隔离（防 list 误回 sample） |
| `client/src/pages/analysis/report.tsx` | 收到 `id='sample'` 时顶部展示「示例报告」徽章 + 替换 CTA 文案 |

### 2.2 数据隔离

- `analysis_service.list_analyses` 默认带 `SwingAnalysis.is_sample.is_(False)` 过滤，确保历史列表绝不混入示例
- 示例 JSON 在 `sample_fixture.build_sample_report` 内**纯内存**构造，**不写 DB / 不扣配额**

---

## 3. 验收证据

### 3.1 自动化测试

| 测试文件 | 覆盖点 |
|---------|--------|
| `backend/tests/test_analyses_sample.py`（如有） | `GET /v1/analyses/sample` 不需登录、`id='sample'`、字段完整 |
| `backend/tests/test_analyses_lifecycle.py::test_list_analyses_*` | `is_sample=False` 过滤生效（用户列表不会回到 sample 数据） |

### 3.2 集成证据

- CVM `curl https://api.birdieai.cn/v1/analyses/sample` 可直拉示例（**匿名**）；
- 客户端首页 / 引导页 / 拍摄页底部「先看示例」按钮可观察 `id=sample` 报告页正确渲染；
- 任意新登录用户 `GET /v1/analyses?page=1` 返回 `total=0`，**示例不计入**用户历史；
- 配额接口 `GET /v1/users/me/analysis-quota` 在示例观看前后保持不变。

### 3.3 已知 backlog

- 示例报告的**视频与骨骼叠加资源**仍是当前 mock 期产物（≤24fps），W6 真引擎产品力 / **Q-B4** 完成后切换为真分析的快照
- 「先看示例」入口埋点（`page_sample_view`）已有，仍待 W8-T5 metrics 看板呈现

---

## 4. 签字栏

| 角色 | 姓名 | 日期 | 备注 |
|------|------|------|------|
| 产品 |  |  |  |
| 工程 |  |  |  |
