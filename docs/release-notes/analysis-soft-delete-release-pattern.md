# 分析报告软删除 · 发版模式约定

> **用途**：含「数据库结构 + 后端 API + 小程序」的分析报告**用户侧软删除**能力上线时，统一 **交付档位、发布顺序、验收与回滚**，避免漏迁移、契约漂移或与支付等模块交叉翻车。  
> **维护**：软删除语义或依赖模块有重大变更时，同步更新本文。

---

## 1. 交付档位（Release tiers）

采用 **同一大版本内分档**：上一档未绿，不宣称下一档完成。

| 档位 | 名称 | 必须满足 | 说明 |
|------|------|----------|------|
| **R0** | 可发版（阻断项） | 迁移已执行；列表/详情/状态/进步曲线对用户隐藏已删记录；`DELETE` 可用且幂等；公开分享报告对已删 `404`；训练/邀请侧与已删记录无错误引用 | **缺任一项不准上生产** |
| **R1** | 同版建议 | `docs/02-API接口设计文档.md` §3.4a、`docs/03-数据库设计文档.md` swing_analyses 与迁移号一致；`backend/tests/test_analysis_soft_delete.py` 在目标环境跑绿；客户端删除入口已联调 | 与 R0 **同一次发布窗口**完成，除非有明确豁免（需留记录） |
| **R2** | 后续迭代（不挡发版） | 错误码与 `analysis` 模块对齐（如对话上下文已删分析从 `40401` 统一为 `40402`）；发消息路径对 `ChatSession.context_analysis_id` 指向已删记录的收敛策略；`total_analyses` 等统计是否与软删一致的产品结论与实现 | 独立 PR / 里程碑，**不**列入 R0 gate |

---

## 2. 发布编排顺序（固定）

对 **本能力** 推荐严格按序执行（与全量业务发版叠加时，**DB 迁移仍须最先**）：

1. **数据库**：`alembic upgrade head`，确保包含 `0010_swing_analysis_deleted_at`、`0011_list_alive_ix`、`0012_ver_num_w128`（或当前链上等价修订；旧版超长 revision id 已改为短 ID 以避免 `alembic_version` VARCHAR(32) 报错）。  
2. **后端**：部署带软删除逻辑的 API / `analysis_service` / 横向模块（share / chat / training / invitation）。  
3. **小程序**：发版包内 `删除` 与 `DELETE` 调用、历史/报告页二次确认已含。  

**交叉依赖（与支付同发版时）**：

- 支付分支**仅**以 `POST /payments/orders` 返回的 `mock_mode` 为准，**禁止**用编译期 `PAYMENT_MOCK` 覆盖服务端真/模（见会员页实现与 `docs` 注释）。  
- 真支付上线：构建参数 `TARO_APP_PAYMENT_MOCK=false` 与后端 `WECHAT_PAY_MOCK_MODE=false` **成对**变更，并单独验单。

---

## 3. R0 验证清单（Smoke，可手测）

在**目标环境**用真实小程序账号（非纯 mock 登录，若生产）：

- [ ] **列表**：删除一条已完成分析后，`GET /v1/analyses` 中不再出现，`total` 减少。  
- [ ] **详情**：同一条 `GET /v1/analyses/{id}` 返回 **404**（业务码 `40402`）。  
- [ ] **状态**：进行中任务仍可轮询 `GET …/status`；完成后删除规则符合 §3.4a（进行中删除 `40092`）。  
- [ ] **公开链接**：`GET /v1/analyses/{id}/public` 对已删为 **404**。  
- [ ] **幂等**：同一 `id` 第二次 `DELETE` 仍 **200**。  
- [ ] **他人订单**：他人 `DELETE` 本人分析 → **403**。  
- [ ] **训练**：若当周计划 `source_analysis_id` 指向该分析，删除后库里该字段被清空（或等价行为），且不报错。  

自动化：`make backend-test` 中含 `test_analysis_soft_delete`（或等价筛选）通过。

---

## 4. 回滚策略

| 场景 | 建议 |
|------|------|
| **仅代码回滚** | DB 列 `deleted_at` / 索引通常 **保留**（兼容旧代码忽略列）；旧后端不再写 `deleted_at`，已删用户侧仍看不到需新接口修复时再发版。 |
| **迁移曾执行且需降级库结构** | 慎用 `alembic downgrade`；生产需备份与窗口评估；一般不建议只为软删除 downgrade。 |
| **迁移文件曾上线后又删修订导致版本链断裂** | 按运维规范 repair `alembic_version`，勿手改业务数据表结构。 |

---

## 5. 与本仓库其它清单的关系

- 真机 / 测试环境通用体检：[`W8-preflight-checklist.md`](./W8-preflight-checklist.md)。  
- 小程序正式发布傻瓜清单：[`go-live-weapp-fool-checklist.md`](./go-live-weapp-fool-checklist.md)。  
- Git / PR / 分支节奏：[`docs/10-Git协作规范.md`](../10-Git协作规范.md)。

本文 **不替代** 上述全局清单；软删除发版时在 PR「自测记录」中 **`勾选 §3 或贴命令输出`**，并在模板里注明「遵循 analysis-soft-delete-release-pattern · R0/R1」。

---

## 6. R2  backlog（备忘，不发版阻断）

跟踪即可（工单标题建议带 `[analysis-soft-delete-R2]`）：

1. `chat_service._validate_context_analysis` 与 analysis 模块统一 **40402**（若产品确认）。  
2. 旧会话携带已删 `context_analysis_id` 时的 UX / 服务端校验策略。  
3. `users.total_analyses`（或其它缓存计数）是否与「用户可见分析数」对齐的产品结论与实现。
