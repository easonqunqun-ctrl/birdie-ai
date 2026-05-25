# P2-M13-10 · 教练旁观入口（约球教学 hook，可选） · 启动包（W34 起跑）

> 版本：v0.1（2026-05-25）
> 上游真源：[`docs/23 §9.10`](../23-二期可编码规格说明书.md#910-p2-m13-10--教练旁观入口约球教学-hook可选)
> 前置：M8-01~03 + M13-04

---

## 一、文档目的与边界

为 **P2-M13-10**（**可选 feature**，**可推后到 v0.2.2**）落地 W34-W36 客户端 + 后端 SOP，让教练能"旁观"自己学员的约球，主动联系陪练（不直接介入隐私）。

### 边界（不做）

- 不修改 docs/22/23/06 字段
- 不允许教练主动加入未授权学员的约球
- 不开放给"非自己学员"

---

## 二、现状盘点

- M8 师生绑定关系已就位
- M13-04 邀请已就位
- 一期教练无 M13 入口

### 缺口

3 个 FR 全部新增（教练侧）。

---

## 三、模块设计

### 3.1 新增

| 模块 | 路径 | 工程量 |
| --- | --- | --- |
| API | `GET /v1/coach/students/{id}/meetups` | 0.3 PW |
| 服务 | filter by relation | 0.2 PW |
| 客户端 | 学员详情 → "近期约球"卡 | 0.4 PW |
| 主动联系陪练 hook | 复用 M13-04 邀请 | 0.3 PW |
| 隐私守门 | 仅展示已 opt-in 学员 | 0.2 PW |

**合计：~1.5 PW（可推后到 v0.2.2）**

### 3.2 隐私 + 角色守门

```python
def list_student_meetups(coach_id: str, student_id: str):
    # 1. 校验师生关系
    relation = require_active_relation(coach_id, student_id)
    # 2. 校验学员是否 opt-in M13
    profile = require_consent(student_id, 'meetup')
    # 3. 校验学员是否 opt-in 教练旁观
    if not profile.privacy_payload.get('coach_spectator_optin'):
        raise ForbiddenError(40334, '学员未授权教练旁观')
    # 4. 返回该学员发起的约球（去识别其他用户）
    meetups = query_meetups_by_user(student_id)
    return [anonymize_others(m, viewer_role='coach_spectator') for m in meetups]
```

### 3.3 学员侧授权

```
[设置 - 隐私] 是否允许我的教练查看我的约球记录？
  [允许] / [拒绝（默认）]
```

### 3.4 主动联系陪练

教练看到学员发起的约球后 → 可一键发起 M13-04 邀请（自己以教练身份 + 学员一起）。

---

## 四、字段 v0.1

```python
# user_profiles_v2.privacy_payload
coach_spectator_optin: bool  # default false
```

API：
```
GET /v1/coach/students/{id}/meetups?page=
```

错误码：40334

---

## 五、验证数据

- 师生 + opt-in 学员 → 旁观成功（AC-1）
- 未 opt-in 学员 → 40334（AC-2）
- 学员可随时撤销（AC-3）

---

## 六、W34-W36 周计划

| 周 | 任务 |
| --- | --- |
| W34 | API + service |
| W35 | 客户端 UI + 学员设置 |
| W36 | 联系 hook + AC |

---

## 七、责任 / 风险 / 验收

### 责任

| 角色 | 责任 |
| --- | --- |
| 后端 | API + 守门 |
| 客户端 | 教练工作台 + 学员设置 |
| 法务 | opt-in 文案 |

### 风险

| ID | 风险 | 兜底 |
| --- | --- | --- |
| R-01 | 学员不知道被旁观 | 默认 false + 文案明示 |
| R-02 | 教练打扰学员社交 | 仅"联系陪练"，不直接介入约球 |
| R-03 | 评审中砍掉 | 接受推后到 v0.2.2 |
| R-04 | 师生关系解除 | 自动撤销旁观权 |

### AC

- [ ] AC-1 旁观成功
- [ ] AC-2 未授权 40334
- [ ] AC-3 学员可撤销

---

## 八、附录

| 任务 | 关系 |
| --- | --- |
| P2-M8-01~03 师生 | 关系基础 |
| P2-M13-04 邀请 | 联系 hook |
| P2-M13-05 隐私 | opt-in 框架 |

---

## 九、变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-05-25 | 初版 |
