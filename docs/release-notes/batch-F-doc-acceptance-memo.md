# Batch-F 文档验收 · 勾选同步纪要

> **执行日期**：2026-05-21  
> **对应队列**：**Batch-F** · **DOC-04** · **par-C1～C3** · **O-11 / O-12 / P-04**  
> **代码版本**：`main @ ca168ab`

---

## 1. 结论

| 项 | 结果 |
|----|------|
| **par-C1** 账号注销 | ✅ 已于 2026-05-20 完成（纪要 + 12 pytest） |
| **par-C2** 会员到期/降级 | ✅ 工程 + 产品 2026-05-22 |
| **par-C3** 示例视频 §3.6 | ✅ 工程 + 产品 2026-05-22 |
| **`docs/01` 勾选同步** | O-11 / O-12 / P-04 → `[x]`；P-03 / DOC-02 / O-14 → `[~]` 更新脚注 |
| **DOC-05 巡检** | 本节即发版前脚注↔主行对齐；无新增「脚注已实现、主行仍 `- [ ]`」项 |

**整体判定**：**文档债已清**；par-C2/C3 **产品已于 2026-05-22 签字**（见 [`v1.2.13-phase1-closure-memo.md`](./v1.2.13-phase1-closure-memo.md)）。

---

## 2. `docs/01` 回填清单

| 位置 | 变更 | PLAN-ID |
|------|------|---------|
| §3.5 到期提醒 | 脚注更新：Batch-B 多档 csv + 站内弹窗 | DOC-02 |
| §6.3 进步曲线 | P-03 `[~]` Batch-C-2；**P-04 `[x]`** | P-03 / P-04 |
| §7.1 分享验收 | **O-11 `[x]`** 海报 · **O-12 `[x]`** 小程序码 | O-11 / O-12 |
| §7.1 延后清单 | 海报/小程序码移出「仍延后」 | Q-B2 |
| §8.4 到期提醒 | 脚注对齐 Batch-B | O-14 |

---

## 3. 验收纪要签字状态

| 纪要 | 工程 | 产品 |
|------|------|------|
| [par-C1](./par-C1-account-deletion-acceptance-memo.md) | ✅ | （已闭环） |
| [par-C2](./par-C2-membership-expiry-acceptance-memo.md) | ☑ 2026-05-21 | ✅ 陈 2026-05-22 |
| [par-C3](./par-C3-sample-video-acceptance-memo.md) | ☑ 2026-05-21 | ✅ 陈 2026-05-22 |

**产品签字动作**：打开上述 par-C2/par-C3 纪要 §4 表格，确认真机/体验版抽测无异议后填姓名与日期。

---

## 4. 仍开放的文档/产品项（不阻塞体验版）

| 项 | 说明 |
|----|------|
| 朋友圈封面 | Skyline / share-timeline（Q-B2 余量） |
| 打卡月历 UI | Q-B3 余量 |
| papay 委托扣费真签约 | Q-B5 / O-13 开通侧 |
| 订阅消息真机送达 | 运营模板审核 + 用户授权次数 |

---

## 5. 关联

- [`docs/19` §6.5 / §6.5b](../19-产品开发迭代计划-当前队列.md)
- [`parallel-engineering-backlog.md`](./parallel-engineering-backlog.md) C1–C3
- [`batch-A-production-preflight-acceptance-memo.md`](./batch-A-production-preflight-acceptance-memo.md)
