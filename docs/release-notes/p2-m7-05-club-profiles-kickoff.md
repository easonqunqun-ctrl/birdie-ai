# P2-M7-05 · 球杆差异化标尺 · 启动包（W17 起跑）

> 版本：v0.1（2026-05-25）
> 状态：启动输入稿
> 适用范围：二期 Phase 2.1 期间，落地按球杆类别（driver / wood / hybrid / iron / wedge）独立的 `PHASE_WEIGHTS` 与 ideal 范围
> 上游真源（待 PR #20 合并后生效）：[`docs/23 §3.5 · P2-M7-05 · 球杆差异化标尺`](../23-二期可编码规格说明书.md#35-p2-m7-05--球杆差异化标尺driver--iron--wedge--hybrid-独立-ideal)
> 前置 kickoff：[`p2-m7-01-ecs-v2-kickoff.md`](./p2-m7-01-ecs-v2-kickoff.md)（**硬依赖**：ECS v2 4 杆型分桶各 ≥20 段，W21 起可用）；[`p2-m7-04-camera-angle-calibration-kickoff.md`](./p2-m7-04-camera-angle-calibration-kickoff.md)（**软依赖**：标尺二维 angle × club_category，结构借鉴）

---

## 一、文档目的与边界

### 1.1 目的

为 **P2-M7-05 球杆差异化标尺**落地一份「**W17 即可起跑、W22 5 杆型独立标尺端到端就绪**」的算法启动 SOP，让算法团队明确：

- 一期 `club_type` **入库但未参与评分**的现状与痛点
- 派生层 `club_profiles.to_club_category()` 单一映射规约（一期 22 种 club_type → 6 个 category）
- 5 套 `PHASE_WEIGHTS_BY_CATEGORY` + 关键特征差异化 ideal v0.1 草案（W19 编码用；W22 ECS 标定后替换）
- 与 P2-M7-04 双套 angle 标尺的叠加规则（最终为 `(angle, category)` 二维选套）
- ECS v2 分桶要求（AC-1）+ 单测覆盖率 ≥90%（AC-3）

### 1.2 边界（**不**做项）

| 不做 | 原因 |
| --- | --- |
| 不修改 [`docs/22`](../22-二期开发迭代计划.md) / [`docs/23`](../23-二期可编码规格说明书.md) / [`docs/05`](../05-AI模型技术规格文档.md) 任何字段 | 避免与 #18 / #19 / #20 race |
| 不新增 DB 列 / 接口字段 | `club_type` 一期已入库；`club_category` 应用层派生不入库（详 §4.2） |
| 不实现推杆独立标尺 | P2-M7-11 独立 pipeline 任务负责 putter；本任务**不**为 putter 出 `PHASE_WEIGHTS_BY_CATEGORY['putter']` |
| 不动客户端 `params.tsx` 球杆选择 UI | 一期 22 种 club_type 选项保持不变 |
| 不新增 issue 类型 | M7-10 诊断规则 V2 引擎负责扩规则；本任务只挂阈值按 category 微调（W21 评审后决定） |

### 1.3 与其他文档的关系

```
docs/23 §3.5          ← 需求真源
p2-m7-01-ecs-v2       ← ECS v2 杆型分桶 ≥20 段/型（AC-1 验证集真值）
p2-m7-04-camera-angle ← 双套 angle 标尺；本任务在 angle 套基础上再分 category
本文件                 ← 派生映射 + 5 套权重 v0.1 + 周计划
  ↓ W22 回流
docs/05 §8.4（已就位）← 球杆差异化标尺章节定稿
docs/23 §3.5         ← AC 勾选完成
docs/20 §3.2（拟）    ← Calibration 主线进度同步
```

---

## 二、现状盘点

### 2.1 一期 `club_type` 数据流

```
client/pages/analysis/params.tsx     用户从 CLUB_TYPE_GROUPS 选 22 种球杆之一
  ↓ POST /v1/analyses { club_type: "iron_7" }
backend swing_analyses.club_type     入库（String(20)）
  ↓ AnalyzeRequest.club_type
ai_engine/app/pipeline/real_pipeline.py
  ↓ preprocess → pose → phases → features → scoring → diagnose
  ❌ req.club_type **未被读取**
  ↓
constants.PHASE_WEIGHTS（单套）+ FEATURES.ideal_min/max（单套）→ score_overall
```

**结论**：用户用 Driver 拍挥杆与用 7 号铁拍挥杆，**走同一套 PHASE_WEIGHTS + 同一套 ideal**。Driver 应宽容的 spine_angle 被铁杆标尺挑刺；Wedge 短挥应短促的 tempo_ratio 被 driver 标尺判"节奏太快"。

### 2.2 一期相关代码

| 文件 | 行数 / 要点 | V2 改造 |
| --- | --- | --- |
| `client/src/types/api.ts` L10-25 | `ClubType` 联合类型 22 值（`driver` / `fairway_wood` / `iron_3..9` / `wedge_*` / `putter` 等） | 不动 |
| `client/src/types/analysis.ts` L197-220 | `CLUB_TYPE_LABEL` / `CLUB_TYPE_GROUPS` UI 文案与分组 | 不动 |
| `client/src/pages/analysis/params.tsx` L78 | `useState<ClubType>('iron_7')` 默认 7 号铁 | 不动 |
| `client/src/pages/analysis/report.tsx` L173 / L739 | `CLUB_TYPE_LABEL[report.club_type]` 仅展示文案 | **小改**：加 "按 {球杆} 评分" 文案（AC-2） |
| `backend/app/models/analysis.py` L62 | `club_type: Mapped[str] = mapped_column(String(20))` | 不动 |
| `ai_engine/app/schemas.py` L14 | `club_type: str` 入参 | 不动；**新增** `to_club_category(club_type)` 调用 |
| `ai_engine/app/pipeline/constants.py` L40-47 | `PHASE_WEIGHTS` 单套 | **保留**作为 fallback；**新增** `PHASE_WEIGHTS_BY_CATEGORY` |
| `ai_engine/app/pipeline/constants.py` L93-265 | 15 特征 `FEATURES` 元数据，`ideal_min/max` 单套 | **新增** `FEATURES_IDEAL_OVERRIDE_BY_CATEGORY` 仅覆盖差异特征 |
| `ai_engine/app/pipeline/scoring.py` | `score_phase` / `score_overall` 未接 club_category | **改造**：可选 `category` 参数；默认 `'iron'`（向下兼容） |
| `ai_engine/app/pipeline/real_pipeline.py` L60 起 | 主入口未读 `req.club_type` 用于评分 | **改造**：派生 category → 传 scoring |

### 2.3 已知缺口（vs docs/23 §3.5 FR）

| FR | 现状 | 缺口 |
| --- | --- | --- |
| FR-1 `club_profiles.py` 提供 `to_club_category()` | ❌ 无 | 新增模块 + 22→6 单元枚举映射 |
| FR-2 ≥5 套独立 `PHASE_WEIGHTS_BY_CATEGORY` | ❌ 单套 | §4.1 v0.1 草案 |
| FR-3 关键特征按 category 覆盖 ideal | ❌ 单套 | §4.2 v0.1 草案 |
| FR-4 报告 UI 展示"按你的 {球杆} 评分" | 仅 club label | report.tsx 加一行文案（M7-05 owner 小改） |
| FR-5 ECS v2 按球杆分桶（每杆型 ≥20 段） | 一期无 | P2-M7-01 FR-1 联动；M7-05 AC-1 验证 |

---

## 三、模块设计

### 3.1 新增模块一览

| 模块 | 路径 | 职责 | 工程量 |
| --- | --- | --- | --- |
| 球杆派生 | `ai_engine/app/pipeline/club_profiles.py` | `to_club_category()` + `PHASE_WEIGHTS_BY_CATEGORY` + `FEATURES_IDEAL_OVERRIDE_BY_CATEGORY` | 2 PD |
| scoring 改造 | `ai_engine/app/pipeline/scoring.py` | `score_phase(..., category=...)` / `score_overall(..., category=...)` | 1.5 PD |
| 管线集成 | `real_pipeline.py` | `category = to_club_category(req.club_type)` → scoring | 0.5 PD |
| 单测 | `tests/pipeline/test_club_profiles.py` | 22 值映射全覆盖 + 评分差异断言 | 1.5 PD |
| ECS 回归 | `ai_engine/app/ecs/club_regression.py` | AC-1 同动作不同 club_type 分差 ≥10 | 1.5 PD |
| 客户端文案 | `client/src/pages/analysis/report.tsx` | "按你的 {球杆} 评分" 一行 | 0.5 PD |

**合计：~7.5 PD**（与 docs/23 §3.5 估时 8 PW 一致；为 W22 ideal 标定调参留 0.5 PW buffer）

### 3.2 `club_profiles.py` 派生映射（W17 冻结）

```python
from typing import Literal

ClubCategory = Literal["driver", "wood", "hybrid", "iron", "wedge", "putter"]

# 一期 22 种 club_type → 6 类 category（与 client/src/types/analysis.ts CLUB_TYPE_GROUPS 对齐）
_CLUB_TYPE_TO_CATEGORY: dict[str, ClubCategory] = {
    # 木杆
    "driver": "driver",
    "fairway_wood": "wood",
    # 铁杆
    "iron_3": "iron", "iron_4": "iron", "iron_5": "iron",
    "iron_6": "iron", "iron_7": "iron", "iron_8": "iron", "iron_9": "iron",
    # 挖起杆
    "wedge_pw": "wedge", "wedge_aw": "wedge",
    "wedge_sw": "wedge", "wedge_lw": "wedge",
    # 混合 / 推
    "hybrid": "hybrid",
    "putter": "putter",
    # ... 详 CLUB_TYPE_GROUPS 全集；W17 实现时与 types/api.ts L10-25 1:1 对齐
}

def to_club_category(club_type: str) -> ClubCategory:
    """22 种 club_type → 6 类 category；未知值 → 'iron' fallback + 写 engine_warnings"""
    return _CLUB_TYPE_TO_CATEGORY.get(club_type, "iron")
```

### 3.3 与 P2-M7-04 双 angle 标尺的叠加

最终评分选套规则为 `(detected_angle, club_category)` 二维：

```python
# scoring.py 改造后
def score_overall(..., angle: str, category: ClubCategory) -> float:
    weights = PHASE_WEIGHTS_BY_CATEGORY[category].get(angle, PHASE_WEIGHTS_BY_ANGLE[angle])
    # category 维度优先；若该 category 未为 angle 单独标定（W22 ECS 数据不足），fallback angle 套
    ...
```

> **写作约定**：本任务**只**出 `PHASE_WEIGHTS_BY_CATEGORY[category]` 单维表；与 angle 维度的笛卡尔积在 M7-04 W19 W19 接入后由 scoring 层组合，不在 club_profiles.py 内表达。

### 3.4 fallback 策略

| 场景 | 行为 |
| --- | --- |
| `club_type` 不在 22 种枚举内（前端 bug 或老数据） | fallback `category='iron'` + `engine_warnings[] += "unknown_club_type"` |
| `category='putter'` 且当前任务范围内 | **路由到 P2-M7-11 推杆 pipeline**（real_pipeline.py 在 preprocess 前分支）；本任务**不**为 putter 计算 PHASE_WEIGHTS |
| 该 category 在 ECS v2 W22 仍未达 ≥20 段（如 hybrid） | `PHASE_WEIGHTS_BY_CATEGORY[hybrid]` 使用 `iron` 的副本 + 文档标记「W26 ECS 补齐后替换」 |

---

## 四、字段 / 配置草案 v0.1（W19 编码初值）

> 数值为算法 PoC 初值；**不**与 [`docs/05`](../05-AI模型技术规格文档.md) §8.4 绑定，待 W22 ECS v2 标定后回流定稿。

### 4.1 `PHASE_WEIGHTS_BY_CATEGORY` v0.1

| 阶段 | driver | wood | hybrid | iron（基线） | wedge | 设计意图 |
| --- | --- | --- | --- | --- | --- | --- |
| setup | 0.13 | 0.13 | 0.14 | 0.15 | 0.18 | wedge 短挥更看站位 |
| backswing | 0.20 | 0.20 | 0.20 | 0.20 | 0.18 | 持平 |
| top | 0.15 | 0.15 | 0.15 | 0.15 | 0.14 | 持平 |
| downswing | 0.28 | 0.27 | 0.26 | 0.25 | 0.22 | driver 力量传递更关键 |
| impact | 0.14 | 0.14 | 0.15 | 0.15 | 0.18 | wedge / 短杆击球点更精确 |
| follow_through | 0.10 | 0.11 | 0.10 | 0.10 | 0.10 | 持平 |

每套和 = 1.0（assert 与一期一致）。**putter 套缺席**（M7-11 负责）。

### 4.2 `FEATURES_IDEAL_OVERRIDE_BY_CATEGORY` v0.1（仅列差异项）

> 未列特征：所有 category **共用** 一期 `FEATURES` 的 `ideal_min/max`。

| 特征 | driver | wood | iron（基线） | wedge | 备注 |
| --- | --- | --- | --- | --- | --- |
| `tempo_ratio` | 2.5-4.0 | 2.3-3.8 | 2.0-3.8 | 1.8-3.2 | wedge 短挥节奏更紧凑 |
| `spine_angle_setup` | 22-32° | 23-33° | 25-35° | 28-38° | wedge 站位更前倾 |
| `shoulder_rotation_top` | 35-100° | 32-95° | 30-95° | 25-85° | wedge 转肩自然较少 |
| `spine_angle_impact_delta` | 0-22° | 0-20° | 0-18° | 0-15° | wedge 更看姿势保持 |
| `head_lateral_shift` | 0-0.10 | 0-0.09 | 0-0.08 | 0-0.06 | wedge 头位稳定要求最严 |

> hybrid 与 wood / iron 之间插值（具体数值 W21 标定）；本表 W19 编码用，W22 ECS 标定后替换。

### 4.3 响应字段（v0.1，不入库）

`AnalyzeResult` 增 `club_category: str`（派生值，便于客户端调试 / 文案选择，**不**写 DB）；客户端可优先使用 `club_type`，无需消费 `club_category`。

---

## 五、验证数据

### 5.1 ECS v2 杆型分桶（AC-1 / AC-3，依赖 P2-M7-01）

| 类别 | 数量要求 | 来源 |
| --- | --- | --- |
| driver | ≥20 段 | P2-M7-01 FR-1 driver 分桶 |
| iron（含 3-9） | ≥20 段 | P2-M7-01 FR-1 iron 分桶 |
| wedge | ≥20 段 | P2-M7-01 FR-1 wedge 分桶 |
| putter（M7-11 用，本任务**不**用） | ≥20 段 | P2-M7-01 FR-1 putter 分桶 |
| wood / hybrid | best-effort ≥10 段 | P2-M7-01 后续扩展 |

### 5.2 同动作不同 club_type 分差测试（AC-1）

| 测试集 | 生成方式 | 期望 |
| --- | --- | --- |
| 同球员同动作打 driver | 自录 ≥3 段 | 同一帧序列用 4 种 category 标尺评分，driver vs iron 综合分差 ≥10 分 |
| 同帧序列伪造 club_type | ECS 样本元数据切换 club_type | 单纯 category 切换可观测分数差 ≥10 分（断言 AC-1） |

存放：`ai_engine/tests/fixtures/club_category/`（**不入库**）

### 5.3 单测覆盖率（AC-3）

- `tests/pipeline/test_club_profiles.py`：
  - 22 种 club_type → category 全枚举覆盖
  - 未知值 fallback `iron` + warning
  - `PHASE_WEIGHTS_BY_CATEGORY` 每套和 = 1.0
  - `FEATURES_IDEAL_OVERRIDE_BY_CATEGORY` 覆盖键全部在 `FEATURES` 中
  - 覆盖率 ≥90%（pytest-cov 报告）

---

## 六、W17-W22 周计划

> **硬门槛**：W22 W22 起 ECS v2 杆型分桶各 ≥20 段可用；driver / iron / wedge 三类齐备即可进入 AC 验证。

| 周 | 任务 | DoD |
| --- | --- | --- |
| **W17** | 本文件评审；冻结 `_CLUB_TYPE_TO_CATEGORY` 22→6 映射；与 P2-M7-04 owner 对齐二维标尺接口 | ☑ 22 值映射表评审通过；☑ scoring 接口签名 review |
| **W18** | `club_profiles.py` 实现 + 单测 22 值覆盖；`PHASE_WEIGHTS_BY_CATEGORY` v0.1 入库 | ☑ 单测 ≥90% 通过；☑ 5 套权重和 = 1.0 |
| **W19** | scoring 改造 + real_pipeline 集成 + 端到端 smoke | ☑ 同一段挥杆按 driver / iron / wedge 评分有可观测差异 |
| **W20** | 客户端 report.tsx 文案 "按你的 {球杆} 评分"；poster / share 文案对齐 | ☑ AC-2 通过；☑ 复用 `CLUB_TYPE_LABEL` |
| **W21** | ECS v2 杆型分桶分布探针 + ideal 调参（v0.1 → v0.2） | ☑ driver / iron / wedge 同动作分差 ≥10（AC-1） |
| **W22** | 与 M7-04 二维联动；docs/05 §8.4 v0.1 → v1.0 回流；engine_version 灰度（M7-14） | ☑ 二维 angle × category 选套联调通过；☑ AC 全勾 |

---

## 七、责任 / 风险 / 验收

### 7.1 责任

| 角色 | 责任 |
| --- | --- |
| 算法 Lead | 总 owner；映射 / 权重 / ECS 标定调参 |
| AI 工程 | scoring 改造 + pipeline 集成 + 单测 |
| 数据 / 教研 | ECS v2 杆型分桶质量；W21 ideal 调参复核 |
| 客户端 | W20 report.tsx 文案；poster / share 同步 |

### 7.2 风险

| ID | 风险 | 兜底 |
| --- | --- | --- |
| R-01 | hybrid / wood 在 ECS v2 W22 仍 <10 段 | fallback iron 套 + 文档标记，W26 补齐后替换 |
| R-02 | category 切换让老用户分数突变（"我上次 7 铁打 80 分，今天换 Driver 突然 60 分"） | 报告页明示"按 {球杆} 评分"；M7-14 灰度 5% 起 |
| R-03 | 与 P2-M7-04 angle 二维叠加导致组合爆炸（6 cat × 3 angle = 18 套） | 仅 driver / iron / wedge × face_on / dtl 全标定（6 套），其余 fallback 维度 |
| R-04 | wedge 用户提交全挥（非短挥），标尺与实际不匹配 | 长期靠 M7-13 多挥识别；MVP 期不识别动作意图，按 club_type 走 |

### 7.3 AC 兜底（复述 docs/23 §3.5）

- [ ] **AC-1**：4 大杆型至少 3 套独立 ideal；同一动作不同 club_type 综合分差 ≥10
- [ ] **AC-2**：客户端报告页明示"按你的 {球杆} 评分"文案
- [ ] **AC-3**：`test_club_profiles.py` 覆盖率 ≥90%

---

## 八、附录

### 8.1 与相邻 PLAN-ID 分工

| 任务 | M7-05 交付 | 下游消费 / 上游依赖 |
| --- | --- | --- |
| P2-M7-01 ECS v2 | 消费杆型分桶 | 验证集真值 |
| P2-M7-04 机位标尺 | 消费 `detected_angle` | 二维 `(angle, category)` 选套 |
| P2-M7-06 置信度 | 提供 `club_category` | confidence 计算可参考 category 数据稀疏度 |
| P2-M7-10 诊断 V2 | 阈值按 category 微调入口 | RuleEngine 接 `category` 上下文 |
| P2-M7-11 推杆 pipeline | category='putter' 路由出口 | 不走本任务标尺 |
| P2-M7-14 engine_version | 标尺挂 `engine_version=v2.0` | 回滚忽略 category，单套兜底 |

### 8.2 ECS manifest 必填字段（杆型子集）

ECS jsonl 须含（与 P2-M7-01 §四 manifest 对齐）：

```jsonc
{
  "club_type": "iron_7",           // 22 值之一（与 client types/api.ts ClubType 对齐）
  "club_category": "iron",         // 派生值；冗余写入便于查询
  "camera_angle": "face_on"
}
```

---

## 九、变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-05-25 | 初版；22→6 映射 + 5 套 PHASE_WEIGHTS_BY_CATEGORY v0.1 + 5 特征 ideal override + W17-W22 周计划 |
| v0.2 | W22 收尾 | ECS 标定后的权重 / ideal 终表回流 docs/05 §8.4；本文件 superseded |
