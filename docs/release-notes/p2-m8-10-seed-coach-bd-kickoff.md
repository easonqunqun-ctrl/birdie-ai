# P2-M8-10 · 教练 BD 工具：5-10 位种子教练入驻 + 一年免费高级权益 · 启动包（W22 起跑）

> 版本：v0.1（2026-05-25）
> 上游真源：[`docs/23 §4.10`](../23-二期可编码规格说明书.md#410-p2-m8-10--教练-bd-工具5-10-位种子教练入驻--一年免费高级权益)
> 前置：DEP-02 教练 BD（产品 + BD 主导）

---

## 一、文档目的与边界

为 **P2-M8-10** 落地 W22-W30 BD + 产品 SOP，完成 5-10 位种子教练招募 + 一年高级权益开通 + NPS 月报机制。

### 边界（不做）

- 不修改 docs/22/23 字段
- 不实现 App 内 NPS 调研（用问卷星 / 微信群）
- 不实现教练独立计费

---

## 二、现状盘点

- 一期 membership 表已有"高级会员"标志位
- M8-01 提供 `coach_profiles.status='active'` + `level` 字段
- 没有 BD 用 lead 跟进 CRM；轻量用飞书多维表代替

### 缺口

- `coach_profiles.level='seed'` 标记位
- 一年权益开通脚本
- NPS 月报模板

---

## 三、模块设计

### 3.1 改造 + 新增

| 模块 | 路径 | 工程量 |
| --- | --- | --- |
| 字段追加 | `coach_profiles.level` 加 'seed' 枚举（M8-01 schema 内追加） | 0 PW（合入 M8-01） |
| 一年权益脚本 | `tools/scripts/grant_seed_coach_premium.py`（新） | 0.3 PW |
| 后台标记 UI | `backend/admin/coaches/list.html` 加"种子"toggle | 0.3 PW |
| NPS 模板 | 飞书多维表 + 问卷星模板 | 0.4 PW（运营） |
| 数据看板 | 飞书多维表 + 一期数据导出 | 0.5 PW |
| BD 物料 | PDF 介绍 + 微信群 SOP | 0.5 PW（运营） |

**合计：~2 PW**（与 docs/23 §4.10 持平）

### 3.2 一年权益开通脚本

```python
# tools/scripts/grant_seed_coach_premium.py
def grant_seed_premium(coach_user_id: str, valid_days: int = 365):
    # 1. 校验 coach_profiles.level='seed' 且 status='active'
    # 2. 写 memberships(user_id, tier='premium', source='seed_coach_bd', valid_until=NOW()+INTERVAL '365 days')
    # 3. 写 audit_log(action='grant_seed_premium', operator_id=admin_id, target_id=coach_user_id)
```

执行：`uv run python tools/scripts/grant_seed_coach_premium.py --coach-id <id>`

### 3.3 NPS 模板（运营产出）

- 问卷星：10 题（NPS + 痛点开放题 + 改进建议）
- 月初 1 号发；7 天回收；月中 15 号汇总月报
- 月报模板：飞书云文档（产品 + BD 共编辑）

### 3.4 数据看板字段（飞书多维表）

| 字段 | 数据源 |
| --- | --- |
| 教练名 | 飞书 |
| 入驻日 | coach_profiles.created_at |
| 学员数 | coach_student_relations(active) |
| 月派发数 | coach_assigned_tasks COUNT |
| 月批注数 | analysis_annotations COUNT |
| 学员 NPS | 飞书手填 |
| 月 NPS | 飞书 |

数据每周一自动 ETL 一次（脚本 + 飞书 webhook）。

---

## 四、字段 v0.1

- `coach_profiles.level` 枚举 v0.1：`junior` / `senior` / `seed`
- 不新增表

---

## 五、验证数据

- 5 位种子教练入驻（AC-1）
- 5 位 premium membership 365 天就位（AC-2）
- 首月 NPS 报告产出（AC-3）

---

## 六、W22-W30 周计划

| 周 | 任务 |
| --- | --- |
| W22 | BD 物料 + 招募启动 |
| W23-W26 | 5 位入驻 + 权益开通 |
| W27-W28 | NPS 调研 + 数据看板 |
| W29 | 首月 NPS 月报 |
| W30 | 调研改进 → 反馈给 M8 各任务 owner |

---

## 七、责任 / 风险 / 验收

### 责任

| 角色 | 责任 |
| --- | --- |
| 产品 + BD | 招募 + 月报 |
| 后端 | 脚本 + 后台 |
| 运营 | NPS + 物料 |

### 风险

| ID | 风险 | 兜底 |
| --- | --- | --- |
| R-01 | 5 位招募延期 | 降到 3 位也启动；不卡 M8 主迭代 |
| R-02 | NPS <50 | 月报 review + 痛点逐项整改 |
| R-03 | 一年免费成本失控 | 单教练 ≤2000 元/年硬上限；超限砍服务 |
| R-04 | 教练流失 | 月度 1v1；流失教练学员转移 SOP |

### AC

- [ ] AC-1 5 位入驻
- [ ] AC-2 权益就位
- [ ] AC-3 NPS 首月报告

---

## 八、附录

| 任务 | 关系 |
| --- | --- |
| P2-M8-01 状态 | coach_profiles.level 字段 |
| P2-M8-02~07 主功能 | 种子教练即用户验证 |
| DEP-02 | 总入口 |

---

## 九、变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-05-25 | 初版；招募 + 权益 + NPS |
