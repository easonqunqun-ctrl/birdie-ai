# ENG-06 · 争议样本周更模板

> **位置**：`docs/release-notes/eng-06-disputed-sample-weekly-template.md`
> **配套**：`docs/19-产品开发迭代计划-当前队列.md` §6.3 ENG-06；`docs/20-AI引擎产品力迭代设计.md` 标定集
> **频率**：每周**周二上午**收口，周四同步给产品 + AI 工程；**首版样例附在文末**
> **触发条件**：当周 `v2_count ≥ 5` 且至少 1 条争议反馈（用户「这条不准」按钮 / 客服上传 / 教练抽审）

---

## 0. 为什么有这件事

V2 引擎上线后，**争议样本**（用户/教练判定 AI 误判的真实视频）是产品力迭代的最值钱信号——比纯 metrics 更直接告诉我们：
- 哪些 issue 类型 V2 还在漏覆盖（`v2_enrich_fallback_count`）
- 哪些 trust tier 实际不可信（用户标"低可信曲线点"反而打高分）
- 哪些 camera_angle 检测在边界场景失灵
- 哪类 club_type 的标定权重需要调

**但这是个工程债**：每周都要从一堆视频里挑、标、归档、给工程能用的格式。本模板把流程写死，让运营 / 产品同学**每周复制粘贴半小时收口**。

---

## 1. 数据源

按优先级倒序：

| 优先级 | 来源 | 频次 | 收集渠道 |
|---|---|---|---|
| P0 | 用户 in-app「这条不准」按钮 | 实时 | `analyses_dispute` 表（W18+ 上线，目前用 feedback 表 source=analysis_dispute）|
| P1 | 教练抽审 | 周 | 教练在飞书群/Notion 提交视频链接 + 标注 |
| P2 | 客服转达 | 不定 | 微信客服记录 → 运营周一汇总 |
| P3 | 工程内部 sample（标定集回归） | 季 | `docs/20` ECS 标定集 |

---

## 2. 周更模板（直接复制改）

```markdown
## ENG-06 争议样本周报 · W{N}（{YYYY-MM-DD} ~ {YYYY-MM-DD}）

### 数据
- v2_count（本周新增）：{N}
- 争议反馈数：{N}（in-app {N} / 教练 {N} / 客服 {N}）
- 已归档样本数：{N}（写得动的；不达标的写"待补"）

### 样本明细

| ID | analysis_id | 用户 | club_type | 拍摄角度 | 用户/教练判定 | AI 判定 | 主要问题 | 处理结论 |
|----|-------------|------|-----------|----------|---------------|---------|----------|----------|
| S{N}-01 | ana_xxx | 教练 A | iron_7 | face_on | "实际站位偏开" | AI 漏报 setup 偏开 | rule yaml 阈值设太松 | 调 setup_open_stance.yml threshold 8°→6° |
| S{N}-02 | ana_yyy | 用户 | driver | down_the_line | "我打得不错你给我中可信" | analysis_confidence=0.62 中可信 | 视频抖 → trust 应进低可信 | 调 IQR motion 阈值 |
| ...    |          |       |          |          |               |         |          |          |

### 行动项
- [ ] {归类 1：rule yaml 阈值调整} → 提 PR，linked PLAN-ID: ENG-04
- [ ] {归类 2：trust tier 公式调整} → 等 D7 监控 + 真实流量证据，留 W{N+2}
- [ ] {归类 3：camera_angle 误判} → 加 CameraAngleAlert hint 文案

### 不入档的视频
- S{N}-XX：用户上传非高尔夫视频 → 走 P-02 拒绝；不入争议库
- S{N}-YY：视频 < 2s 或骨骼检出失败 → 走 ENG-02 质量门禁；不入争议库

### 下周关注
- {主题 A，比如：face_on 站位检测在背光下漏报}
- {主题 B}

---
归档位置：docs/eng-samples/W{N}-{YYYY-MM-DD}/  （仅工程访问；含原视频链接 + 脱敏 user_id）
```

---

## 3. 工程化最低要求（避免变成"又一个不维护的 doc"）

每条样本必须有：

1. **`analysis_id`**（唯一定位 V1 / V2 双引擎产物）
2. **判定者标注**（"AI 漏 X / AI 错 Y / AI 过严"），≤ 30 字
3. **AI 实际输出**（截图主分 + issues 列表 + analysis_confidence 4 个字段）
4. **处理结论 PLAN-ID**（必须落到一个 ENG-04 / ENG-06 / ENG-XX 清单条目；没有就不收）

**反例（不要这样写）**：

> S{N}-XX：用户说不准。AI 给 65 分。建议改一下。

→ 缺 analysis_id、缺具体哪不准、缺改哪个 yaml；属于"投诉而非样本"。

---

## 4. 与现有清单的对接

- 处理结论 PLAN-ID 需要落到一个真实条目 → 查 [`docs/19` §6.3](../19-产品开发迭代计划-当前队列.md#63-主表plan-id)
- 触发 rule yaml 改动 → 走 [`docs/01` §4.5](../01-MVP功能需求规格说明书.md#45-ai-引擎产品力对齐-docs20) 验收
- 触发 trust tier 公式改动 → 进入 [`docs/20`](../20-AI引擎产品力迭代设计.md) §3 Trust 公式表更新

---

## 5. 首版样例（W17 提交，作为下次模板基准）

> W24 首版有结构周报见 [`eng-06-W24-2026-05-29.md`](./eng-06-W24-2026-05-29.md)（争议样本仍为 0，等真实流量）。

| ID | 状态 | 备注 |
|---|---|---|
| — | 空跑 | v2 rollout 5%；触发：v2_count ≥ 5 且 ≥1 争议反馈 |

下次触发条件 → 见 [`docs/release-notes/wait-for-triggers-checklist.md`](./wait-for-triggers-checklist.md) 第 § 等 ENG-06 触发条 → 拉本模板填表 → 进 PR。

---

## 6. 落地清单（流水化每周操作）

```bash
# 周二上午 9:00 跑这个
TARGET_WEEK=W$(( ($(date +%V) - 36) % 52 ))
DATE=$(date +%Y-%m-%d)
cp docs/release-notes/eng-06-disputed-sample-weekly-template.md \
   docs/release-notes/eng-06-${TARGET_WEEK}-${DATE}.md
# 编辑新文件 → fill 数据 → 提 PR `docs(eng-06): ${TARGET_WEEK} disputed sample`
```

后续把 `cp` 替换成自动化 GitHub Action（W18+ 自动从 feedback 表抽 SQL → md fragment）。
