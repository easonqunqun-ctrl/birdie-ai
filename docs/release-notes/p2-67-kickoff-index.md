# Phase 2 · 67 篇 Kickoff 启动包总索引（v0.1.1）

> 版本：v0.1.1（2026-05-25）
> 来源计划：[`p2-63-kickoff-rollout`](../../.cursor/plans/p2-63-kickoff-rollout_566c0403.plan.md)
> 上游真源（待 #20 合并后生效）：`docs/23-二期可编码规格说明书.md` §三 ~ §十
> 文档同步真源（待 #19 合并后生效）：`docs/22-二期开发迭代计划.md` §六

---

## 一、说明

本文档是「Phase 2 · 63 篇 Kickoff 全量推进计划」交付的**总索引**。计划起包 63 篇（M7-05 起的全部新任务）；加上一期评审已落地的 M7-01~04 四篇先行包，**Phase 2 全套 67 篇 kickoff 启动包**全部以独立 PR 方式提交。

> **v0.1.1 修订**：review 阶段定位 plan §二 Wave-1~5 漏列 P2-M9-06，已于 [#89](https://github.com/easonqunqun-ctrl/birdie-ai/pull/89) 补录；本索引同步把 66 → 67，并修正 §三 关于 M9 的注释。

每篇 kickoff 文档：
- 落在 `docs/release-notes/p2-mX-NN-<slug>-kickoff.md`
- 遵循 8 节模板（M7-04 同款）：文档目的与边界 / 现状盘点 / 模块设计 / 字段草案 / 验证数据 / 周计划 / 责任分工 / 风险与回滚
- 引用 `docs/23 §三~§十` 对应章节作为上游真源
- 独立 PR 评审，零交叉合并冲突

---

## 二、Wave 与 PR 索引

### Wave-0：M7-01~04（已先行落地，4 篇）

| Kickoff | PR | 起跑周 |
| --- | --- | --- |
| P2-M7-01 ECS v2 标定集采集 | [#22](https://github.com/easonqunqun-ctrl/birdie-ai/pull/22) | W14 |
| P2-M7-02 视频读取增强 | [#23](https://github.com/easonqunqun-ctrl/birdie-ai/pull/23) | W14 |
| P2-M7-03 错误码扩展 | [#24](https://github.com/easonqunqun-ctrl/birdie-ai/pull/24) | W18 |
| P2-M7-04 机位独立标尺 | [#25](https://github.com/easonqunqun-ctrl/birdie-ai/pull/25) | W17 |

### Wave-1：Phase 2.0 / 2.1 起跑 + 基础设施（7 篇）

| Kickoff | PR | 起跑周 |
| --- | --- | --- |
| P2-M7-05 球杆差异化标尺 | [#26](https://github.com/easonqunqun-ctrl/birdie-ai/pull/26) | W17 |
| P2-M7-06 置信度上链路化 | [#27](https://github.com/easonqunqun-ctrl/birdie-ai/pull/27) | W17 |
| P2-M7-14 engine_version + AB 灰度 | [#28](https://github.com/easonqunqun-ctrl/birdie-ai/pull/28) | W14 |
| P2-M9-01 user_profiles_v2 + user_clubs 数据模型 | [#29](https://github.com/easonqunqun-ctrl/birdie-ai/pull/29) | W17 |
| P2-M9-03 onboarding 2.0（差点/身体/利手/伤病） | [#30](https://github.com/easonqunqun-ctrl/birdie-ai/pull/30) | W19 |
| P2-M11-01 课程 4 张表数据模型 | [#31](https://github.com/easonqunqun-ctrl/birdie-ai/pull/31) | W17 |
| P2-M12-01 球手 6 张表数据模型 | [#32](https://github.com/easonqunqun-ctrl/birdie-ai/pull/32) | W17 |

### Wave-2：M7 反馈链 + M8 教练基座 + M9/M11/M12 内容（9 篇）

| Kickoff | PR | 起跑周 |
| --- | --- | --- |
| P2-M7-15 用户反馈回流 ECS 候选池 | [#33](https://github.com/easonqunqun-ctrl/birdie-ai/pull/33) | W30 |
| P2-M9-02 装备清单 UI | [#34](https://github.com/easonqunqun-ctrl/birdie-ai/pull/34) | W20 |
| P2-M9-04 目标 / 训练偏好 | [#35](https://github.com/easonqunqun-ctrl/birdie-ai/pull/35) | W22 |
| P2-M9-05 常去球馆字段 | [#36](https://github.com/easonqunqun-ctrl/birdie-ai/pull/36) | W23 |
| P2-M11-02 7 阶课程内容生产 | [#37](https://github.com/easonqunqun-ctrl/birdie-ai/pull/37) | W24 |
| P2-M12-02 球手镜头首批入库 | [#38](https://github.com/easonqunqun-ctrl/birdie-ai/pull/38) | W22 |
| P2-M8-01 教练数据模型 + 资质审核 | [#39](https://github.com/easonqunqun-ctrl/birdie-ai/pull/39) | W17 |
| P2-M8-02 教练身份切换 UI | [#40](https://github.com/easonqunqun-ctrl/birdie-ai/pull/40) | W22 |
| P2-M8-03 学员双向 opt-in 绑定 | [#41](https://github.com/easonqunqun-ctrl/birdie-ai/pull/41) | W22 |

### Wave-3：M7 算法重头 + M8 教学闭环 + M10/M11/M12 体验（15 篇）

| Kickoff | PR | 起跑周 |
| --- | --- | --- |
| P2-M7-07 阶段分割 V2 | [#42](https://github.com/easonqunqun-ctrl/birdie-ai/pull/42) | W22 |
| P2-M7-08 新特征 5 个 | [#43](https://github.com/easonqunqun-ctrl/birdie-ai/pull/43) | W26 |
| P2-M8-04 报告语音 + 涂鸦批注 | [#44](https://github.com/easonqunqun-ctrl/birdie-ai/pull/44) | W23 |
| P2-M8-05 作业派发 | [#45](https://github.com/easonqunqun-ctrl/birdie-ai/pull/45) | W25 |
| P2-M8-06 学员看板 | [#46](https://github.com/easonqunqun-ctrl/birdie-ai/pull/46) | W26 |
| P2-M8-07 教学报告（LLM+PDF） | [#47](https://github.com/easonqunqun-ctrl/birdie-ai/pull/47) | W30 |
| P2-M8-08 上传素材审核 | [#48](https://github.com/easonqunqun-ctrl/birdie-ai/pull/48) | W25 |
| P2-M8-09 教练侧无配额 | [#49](https://github.com/easonqunqun-ctrl/birdie-ai/pull/49) | W29 |
| P2-M8-10 教练 BD 工具 | [#50](https://github.com/easonqunqun-ctrl/birdie-ai/pull/50) | W22 |
| P2-M10-01 推杆模式 UI | [#51](https://github.com/easonqunqun-ctrl/birdie-ai/pull/51) | W21 |
| P2-M10-02 切杆模式 UI | [#52](https://github.com/easonqunqun-ctrl/birdie-ai/pull/52) | W22 |
| P2-M11-03 学习路径 UI | [#53](https://github.com/easonqunqun-ctrl/birdie-ai/pull/53) | W28 |
| P2-M11-04 阶段考核 | [#54](https://github.com/easonqunqun-ctrl/birdie-ai/pull/54) | W30 |
| P2-M11-05 证书 / 勋章 | [#55](https://github.com/easonqunqun-ctrl/birdie-ai/pull/55) | W32 |
| P2-M11-06 教练定制课程 | [#56](https://github.com/easonqunqun-ctrl/birdie-ai/pull/56) | W33 |
| P2-M9-06 教练侧只读视图（补录） | [#89](https://github.com/easonqunqun-ctrl/birdie-ai/pull/89) | W26 |

### Wave-4：长尾算法 + 社交全套 + M12/M10 收尾（27 篇）

| Kickoff | PR | 起跑周 |
| --- | --- | --- |
| P2-M7-09 杆/球追踪 | [#57](https://github.com/easonqunqun-ctrl/birdie-ai/pull/57) | W26 |
| P2-M7-10 诊断规则 V2 引擎 | [#58](https://github.com/easonqunqun-ctrl/birdie-ai/pull/58) | W28 |
| P2-M7-11 推杆 pipeline | [#59](https://github.com/easonqunqun-ctrl/birdie-ai/pull/59) | W22 |
| P2-M7-12 切杆 pipeline | [#60](https://github.com/easonqunqun-ctrl/birdie-ai/pull/60) | W24 |
| P2-M7-13 试挥 / 多挥杆识别 | [#61](https://github.com/easonqunqun-ctrl/birdie-ai/pull/61) | W28 |
| P2-M7-16 用户水平差异化文案 | [#62](https://github.com/easonqunqun-ctrl/birdie-ai/pull/62) | W36 |
| P2-M10-03 个人 yardage book | [#63](https://github.com/easonqunqun-ctrl/birdie-ai/pull/63) | W30 |
| P2-M10-04 drill 库扩到 25-30 条 | [#64](https://github.com/easonqunqun-ctrl/birdie-ai/pull/64) | W26 |
| P2-M10-05 训练计划支持短杆/推杆 | [#65](https://github.com/easonqunqun-ctrl/birdie-ai/pull/65) | W32 |
| P2-M12-03 资源库 tab | [#66](https://github.com/easonqunqun-ctrl/birdie-ai/pull/66) | W26 |
| P2-M12-04 匹配算法 | [#67](https://github.com/easonqunqun-ctrl/birdie-ai/pull/67) | W30 |
| P2-M12-05 并排叠加 + 雷达图 | [#68](https://github.com/easonqunqun-ctrl/birdie-ai/pull/68) | W32 |
| P2-M12-06 每周精选 banner | [#69](https://github.com/easonqunqun-ctrl/birdie-ai/pull/69) | W34 |
| P2-M12-07 教练 PGC 解说 + LLM | [#70](https://github.com/easonqunqun-ctrl/birdie-ai/pull/70) | W30 |
| P2-M12-08 追平演化动画 | [#71](https://github.com/easonqunqun-ctrl/birdie-ai/pull/71) | W34 |
| P2-M12-09 教练 M8 引用 pro_clip | [#72](https://github.com/easonqunqun-ctrl/birdie-ai/pull/72) | W28 |
| P2-M12-10 收藏 / 想试试看 | [#73](https://github.com/easonqunqun-ctrl/birdie-ai/pull/73) | W34 |
| P2-M13-01 球友约球数据模型 | [#74](https://github.com/easonqunqun-ctrl/birdie-ai/pull/74) | W22 |
| P2-M13-02 球馆名录冷启 | [#75](https://github.com/easonqunqun-ctrl/birdie-ai/pull/75) | W26 |
| P2-M13-03 球友匹配算法 | [#76](https://github.com/easonqunqun-ctrl/birdie-ai/pull/76) | W28 |
| P2-M13-04 邀请流转 | [#77](https://github.com/easonqunqun-ctrl/birdie-ai/pull/77) | W30 |
| P2-M13-05 隐私授权链路 | [#78](https://github.com/easonqunqun-ctrl/birdie-ai/pull/78) | W28 |
| P2-M13-06 风控 | [#79](https://github.com/easonqunqun-ctrl/birdie-ai/pull/79) | W30 |
| P2-M13-07 互评 + 信用积分 | [#80](https://github.com/easonqunqun-ctrl/birdie-ai/pull/80) | W32 |
| P2-M13-08 自助挑战赛模板 | [#81](https://github.com/easonqunqun-ctrl/birdie-ai/pull/81) | W34 |
| P2-M13-09 服务协议 + 未成年 + 女性安全 | [#82](https://github.com/easonqunqun-ctrl/birdie-ai/pull/82) | W28 |
| P2-M13-10 教练旁观入口 | [#83](https://github.com/easonqunqun-ctrl/birdie-ai/pull/83) | W34 |

### Wave-5：RN App 上架（4 篇）

| Kickoff | PR | 起跑周 |
| --- | --- | --- |
| P2-M14-01 M7-M13 在 RN 上 1:1 验证 | [#84](https://github.com/easonqunqun-ctrl/birdie-ai/pull/84) | W30 |
| P2-M14-02 App Store 上架 | [#85](https://github.com/easonqunqun-ctrl/birdie-ai/pull/85) | W38 |
| P2-M14-03 安卓三市场上架 | [#86](https://github.com/easonqunqun-ctrl/birdie-ai/pull/86) | W38 |
| P2-M14-04 Apple IAP 不做（决策备忘） | [#87](https://github.com/easonqunqun-ctrl/birdie-ai/pull/87) | W38 |

---

## 三、统计

| 维度 | 数 |
| --- | --- |
| 模块数 | 8（M7 / M8 / M9 / M10 / M11 / M12 / M13 / M14） |
| Wave 数 | 5 + Wave-0（4 篇先行包） |
| 新建 kickoff PR | 63（含 M9-06 补录 #89） |
| Wave-0 先行 PR | 4 |
| **总计** | **67** |

| 模块 | docs/23 节数 | PR 篇数 | 状态 |
| --- | --- | --- | --- |
| M7 | 16（§3.1-3.16） | 16（#22-28、#33、#42-43、#57-62） | ✅ 一一对应 |
| M8 | 10（§4.1-4.10） | 10（#39-41、#44-50） | ✅ 一一对应 |
| M9 | 6（§5.1-5.6） | 6（#29-30、#34-36、#89） | ✅ 一一对应 |
| M10 | 5（§6.1-6.5） | 5（#51-52、#63-65） | ✅ 一一对应 |
| M11 | 6（§7.1-7.6） | 6（#31、#37、#53-56） | ✅ 一一对应 |
| M12 | 10（§8.1-8.10） | 10（#32、#38、#66-73） | ✅ 一一对应 |
| M13 | 10（§9.1-9.10） | 10（#74-83） | ✅ 一一对应 |
| M14 | 4（§10.1-10.4） | 4（#84-87） | ✅ 一一对应 |
| **总计** | **67** | **67** | **✅ 全量覆盖** |

> v0.1 → v0.1.1：原索引把 M9 按 5 篇统计并标注"M9-06 并入 M9-01"，review 阶段发现该注释与 docs/23 §5.6 真源不符（M9-06 是字段级 visibility，非 profile schema 扩展）。已通过 [#89](https://github.com/easonqunqun-ctrl/birdie-ai/pull/89) 补录 M9-06 kickoff，本文件同步把统计、模块行、§一 总数全部刷为 67。

---

## 四、与上游真源的回链状态

| 真源 | 状态 |
| --- | --- |
| docs/22 §六 文档同步任务表 状态列 | **待对齐**：本索引 67 篇与"DOC-22-06"行的状态列在 #19 合并后做一次批量刷新 |
| docs/23 §十二 文档变更记录 | **待对齐**：本索引 67 篇与"v0.1.2 (67 PR rollup)"行在 #20 合并后做一次批量刷新 |
| AGENTS.md §9 当需要澄清时 | ✅ 已加入"二期 kickoff 启动包入口"行（路径同步刷为 67） |

---

## 五、维护规则

- **新增 kickoff**：必须按 `docs/release-notes/p2-mX-NN-<slug>-kickoff.md` 命名，本文件追加一行索引
- **kickoff 合并**：在对应行追加"✅ 合并" + 日期；与 docs/22 §六 状态列同步
- **kickoff 弃用**：状态行加"⛔ 弃用 → 转入 v0.2.x"，不删除历史索引（合规审计）
- **本索引文件**：作为长期回链清单，与 docs/19 / docs/22 / docs/23 同等重要

---

## 六、变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-05-25 | 初版（66 PR 起包完成；docs/22/23 对齐待 #19/#20 合并） |
| v0.1.1 | 2026-05-25 | review 修复（review 阶段定位漏列 M9-06）：① 文件改名 `p2-66 → p2-67`；② §一总数 66 → 67；③ §二 Wave-3 末尾追加 P2-M9-06（#89）补录行；④ §三 统计表新增"模块 ↔ 节数 ↔ PR 篇数"一一对应矩阵，撤回原 v0.1 关于"M9-06 并入 M9-01"的错误注释；⑤ §四 状态行数字同步 66 → 67。**无 kickoff 字段 / FR / AC 变更**。 |
