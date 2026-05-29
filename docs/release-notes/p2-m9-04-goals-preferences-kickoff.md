# P2-M9-04 · 目标 + 训练偏好（中长期目标 / 视频 vs 文字派）· 启动包（W22 起跑）

> 版本：v0.1（2026-05-25）
> 状态：启动输入稿
> 适用范围：二期 Phase 2.2 期间，落地短/长期目标 + 训练偏好的 onboarding/UI/LLM 注入
> 上游真源（待 PR #20 合并后生效）：[`docs/23 §5.4 · P2-M9-04`](../23-二期可编码规格说明书.md#54-p2-m9-04--目标--训练偏好中长期目标--视频-vs-文字派)
> 前置 kickoff：[`p2-m9-01-user-profiles-v2-kickoff.md`](./p2-m9-01-user-profiles-v2-kickoff.md)（**硬依赖**：`user_profiles_v2.mid_long_goals` / `training_preference` 字段就绪）+ [`p2-m9-03-handicap-body-handedness-kickoff.md`](./p2-m9-03-handicap-body-handedness-kickoff.md)（onboarding 框架）

---

## 一、文档目的与边界

### 1.1 目的

为 **P2-M9-04** 落地一份「**W22 即可起跑、W24 LLM/课程消费链路就绪**」的客户端 + 后端 + LLM SOP：

- 在 M9-03 6 题 onboarding 之上**追加** 3 题（短期目标 / 长期目标 / 训练偏好）
- 训练偏好结构（style / cadence / preferred_drill_types）
- LLM 对话 / 报告 / 训练计划 prompt 注入
- 与 M11 课程推荐筛选联动

### 1.2 边界（**不**做项）

| 不做 | 原因 |
| --- | --- |
| 不修改 [`docs/22`](../22-二期开发迭代计划.md) / [`docs/23`](../23-二期可编码规格说明书.md) 字段 | 避免与 #18/#19/#20 race |
| 不动 `user_profiles_v2` schema | 由 M9-01 字段已就位 |
| 不实现 M11 课程推荐核心算法 | M11-03 负责；本任务仅提供筛选输入 |
| 不实现 M7-16 LLM 报告差异化文案 | 该任务独立；本任务只提供数据 |

---

## 二、现状盘点

### 2.1 一期 LLM prompt 注入字段

```
backend/app/services/chat_prompt.py
  → 注入 nickname / golf_level / primary_goals / weekly_practice_frequency / total_analyses 等
  ❌ 未注入：handicap / 中长期目标 / 训练偏好（V2 新字段）
```

**结论**：一期 LLM 个性化只用粗粒度 4 档 level + 软偏好；M9-04 上线后注入精细化目标与"视频 vs 文字"偏好，实现"同一动作错误，AI 教练给视频派 / 文字派截然不同的报告"。

### 2.2 已知缺口（vs docs/23 §5.4 FR）

| FR | 现状 | 缺口 |
| --- | --- | --- |
| FR-1 onboarding/画像追加 3 题 | ❌ | onboarding 7-9 题 |
| FR-2 训练偏好结构 (style/cadence/preferred_drill_types) | ❌ | schema + UI |
| FR-3 LLM prompt 注入 | ❌ | chat_prompt.py 改造 |
| FR-4 M11 课程推荐筛选 | ❌ | course_service 查询过滤 |
| FR-5 M7-16 LLM 差异化文案使用 golf_level + handicap | M7-16 待 W34+ 落地 | 仅提供数据；不开发 |

---

## 三、模块设计

### 3.1 新增一览

| 模块 | 路径 | 职责 | 工程量 |
| --- | --- | --- | --- |
| Onboarding 题组件 | `client/src/components/onboarding/GoalsStep.tsx` / `PreferenceStep.tsx`（新） | 短/长期目标 + 偏好 | 1.5 PD |
| Onboarding 主流程改造 | `client/src/pages/onboarding/index.tsx` | 6 → 9 题（与 M9-05 合并落地） | 0.5 PD |
| 编辑页改造 | `client/src/pages/profile/edit.tsx` | 新字段入口 | 0.5 PD |
| 后端 schema | 复用 M9-01 `user_profile_v2` schema | 追加 mid_long_goals / training_preference 字段处理 | 0.3 PD |
| LLM 注入改造 | `backend/app/services/chat_prompt.py` | 新字段进 prompt | 0.7 PD |
| M11 课程筛选 | `backend/app/services/course_service.py` | 按 training_preference 过滤 | 0.7 PD |
| 单测 | client jest + backend pytest | UI + LLM 注入 + 课程筛选 | 1 PD |

**合计：~5 PD**（与 docs/23 §5.4 估时 2 PW 偏宽，含 LLM/课程联动）

### 3.2 训练偏好结构 v0.1

```jsonc
{
  "training_preference": {
    "style": "video",                       // 'video'|'text'|'mixed'
    "cadence": "2x_per_week",                 // 'daily'|'2x_per_week'|'weekly'
    "preferred_drill_types": [
      "rhythm",
      "swing_plane"
    ]                                          // 用户偏好的 drill 类目（与 drills.target_issues 标签对齐）
  }
}
```

存 `user_profiles_v2.training_preference` JSONB 列（M9-01 已规划 VARCHAR(20) → 升级为 JSONB；详 §7.2 R-05）。

### 3.3 LLM prompt 注入草案

```
[既有] 你是 {nickname} 的 AI 高尔夫教练，对方水平 {golf_level}...
[新增] 用户的当前目标：3 个月差点从 {handicap_self} 进步到 {short_term_goal}；
       长期目标：{long_term_goal}。
[新增] 用户偏好 {style}（如 video → 优先给"看视频示范"建议；text → 详细文字描述）。
[新增] 偏好训练频率 {cadence}，drill 类型偏好 {preferred_drill_types}。
```

### 3.4 M11 课程推荐筛选

```python
# course_service.py
def list_recommended_courses(user: User, profile: UserProfileV2) -> list[Course]:
    q = select(Course).where(Course.is_published == True)
    # 按用户偏好 style 过滤
    if profile.training_preference.get("style") == "video":
        q = q.where(Course.cover_url.is_not(None))  # 视频类课程
    # ... 其他筛选
    return ...
```

### 3.5 onboarding 题序（与 M9-03/05 合并后）

| Step | 题目 | 来源 |
| --- | --- | --- |
| 1-3 | level / goals / freq | 一期 |
| 4-6 | handicap / body+handedness / injuries | M9-03 |
| 7 | 短期目标 | M9-04 |
| 8 | 长期目标 | M9-04 |
| 9 | 训练偏好 | M9-04 |

> Step 7-8 可合并到一个组件（GoalsStep）；Step 9 独立。

---

## 四、字段 / 配置草案 v0.1

### 4.1 数据库字段升级

M9-01 规划 `training_preference VARCHAR(20)`；本任务需升级为 `JSONB`（详 §7.2 R-05），通过 alembic 0017 修订 或独立 0020 升级。

### 4.2 配置项

```python
PHASE2_PROFILE_V2_ENABLED: bool = False  # 与 M9-01/02/03 共享
```

---

## 五、验证数据

### 5.1 单测

- 客户端 jest：GoalsStep / PreferenceStep 渲染 + 跳过
- 后端 pytest：chat_prompt 渲染含 short_term_goal / training_preference 字符串
- AC-2 验证脚本：同一动作错误下，video vs text 用户的 LLM 输出差异 ≥ 30%（按字符 diff）

### 5.2 LLM 差异化验证（AC-2）

构造 2 个用户：
- A：training_preference.style=video / goals="差点 22→18"
- B：training_preference.style=text / goals="提升一致性"

同一报告，A 应收到"看 XX 视频示范"建议；B 应收到"按以下文字步骤练习"建议。Diff ≥ 30% 通过。

---

## 六、W22-W24 周计划

| 周 | 任务 | DoD |
| --- | --- | --- |
| **W22** | 评审；GoalsStep / PreferenceStep 设计稿；training_preference JSONB 升级评审 | ☑ 设计走查；☑ schema 升级评审 |
| **W23** | UI 组件 + onboarding 7-9 题集成 + 后端 prompt 注入 | ☑ AC-1 通过 |
| **W24** | LLM 差异化 grep 验证 + M11 课程筛选联动 | ☑ AC-2/3 全勾 |

---

## 七、责任 / 风险 / 验收

### 7.1 责任

| 角色 | 责任 |
| --- | --- |
| 客户端 | onboarding 题组件 + edit 页 |
| 后端 | schema + prompt 注入 + course_service 筛选 |
| LLM / 算法 | prompt 模板设计 + 差异化验证脚本 |

### 7.2 风险

| ID | 风险 | 兜底 |
| --- | --- | --- |
| R-01 | LLM prompt 太长导致延迟 | 仅注入非空字段；总长度 ≤500 token |
| R-02 | "video 派"用户对应资源不足（drill 视频少） | 一期 drills 已重建（drill-demo-video-revamp.md），视频充足；fallback text |
| R-03 | mid_long_goals 自由文本含敏感词 | 走 docs/06 §7.2 内容安全 |
| R-04 | AC-2 30% 差异阈值过严或过松 | W24 校准；可改为人工 review 10 个 case |
| R-05 | M9-01 规划 training_preference 为 VARCHAR(20)，本任务需 JSONB | 独立 alembic 0020 升级；或在 M9-01 W19 时直接定义为 JSONB（推荐——本 kickoff 评审时推动 M9-01 schema 微调） |

### 7.3 AC 兜底（复述 docs/23 §5.4）

- [ ] **AC-1**：onboarding 追加 3 题
- [ ] **AC-2**：video vs text 用户的 LLM 报告文案明显不同
- [ ] **AC-3**：M11 课程推荐响应中含偏好筛选项

---

## 八、附录

### 8.1 与相邻 PLAN-ID 分工

| 任务 | 关系 |
| --- | --- |
| P2-M9-01 数据模型 | 字段就绪；本任务推动 training_preference 改 JSONB |
| P2-M9-03 onboarding | 共享 onboarding 框架（6→9 题） |
| P2-M9-05 常去球馆 | onboarding Step 10（W23 前后） |
| P2-M7-16 LLM 差异化文案 | 消费本任务的 mid_long_goals / training_preference |
| P2-M11-03 学习路径 UI | 消费推荐结果 |

---

## 九、变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-05-25 | 初版；3 题追加 + 偏好 JSONB + LLM 注入 |
