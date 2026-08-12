# P2-M13-04 · 邀请流转 + 一次性微信群链接 + AI 简介 · 启动包（W30 起跑）

> 版本：v0.1（2026-05-25）
> 上游真源：[`docs/23 §9.4`](../23-二期可编码规格说明书.md#94-p2-m13-04--邀请流转--一次性微信群链接--ai-简介自动生成)
> 前置：P2-M13-03 匹配

---

## 一、文档目的与边界

为 **P2-M13-04** 落地 W30-W35 后端 + 客户端 + LLM SOP，邀请双方接受后才生成一次性微信群 QR + AI 简介。

### 边界（不做）

- 不修改 docs/22/23/06 字段
- 不存对方任何联系方式（合规红线）

---

## 二、现状盘点

- M13-01 meetup_invitations 表已就位
- 一期 LLM 可用
- 微信"接龙群链接"/小程序"客服消息"机制可用

### 缺口

6 个 FR 全部新增。

---

## 三、模块设计

### 3.1 新增

| 模块 | 路径 | 工程量 |
| --- | --- | --- |
| Service | `services/meetup_invitation_service.py` | 1.5 PW |
| API | 5 个邀请相关接口 | 0.5 PW |
| QR 生成 | `services/wechat_qr_service.py`（封装） | 0.5 PW |
| LLM 简介 | `services/llm/meetup_intro_prompt.py` | 0.5 PW |
| 客户端 UI | `pages/meetup/invitations/*` | 0.7 PW |
| Cron 失效 | 48h 失效 task | 0.3 PW |
| 单测 | tests | 0.5 PW |

**合计：~3 PW**

### 3.2 邀请状态机

```
pending → accepted → (生成 contact_payload + QR)
       → declined
       → expired (48h 自动)
       → cancelled (发起方撤回)
```

### 3.3 QR 生成（accepted 触发）

```python
def generate_qr_payload(invitation):
    token = secrets.token_urlsafe(16)  # 不可猜
    qr_url = f'/v1/meetup/qr/{token}.png'
    invitation.contact_payload = {
        'wechat_group_qr_token': token,
        'qr_url': qr_url,
        'qr_expires_at': now() + timedelta(hours=48)
    }
```

PR 阻断 grep：禁止 openid / 手机号写入。

### 3.4 LLM 简介

```
基于用户：golf_age={golf_age}, handicap={handicap}, training_freq={freq}
写一段 100 字以内自我简介，给球友看；中性、友好、专业。
```

用户可编辑后才发送。

### 3.5 通知触达

调微信订阅消息 < 30s。

---

## 四、字段 v0.1

```
POST /v1/meetup/invitations Body: { invitee_user_id, venue_id, proposed_time }
POST /v1/meetup/invitations/{id}/accept
POST /v1/meetup/invitations/{id}/decline
POST /v1/meetup/invitations/{id}/cancel
GET  /v1/meetup/invitations?status=
GET  /v1/meetup/qr/{token}.png
```

---

## 五、验证数据

- 双方 accepted 才生成 contact_payload（AC-1）
- 不存对方联系方式（AC-2）
- QR 48h 失效（AC-3）

---

## 六、W30-W35 周计划

| 周 | 任务 |
| --- | --- |
| W30 | 状态机 + service |
| W31 | API + QR |
| W32 | LLM 简介 |
| W33 | UI + 通知 |
| W34 | cron + 单测 |
| W35 | 灰度 + AC |

---

## 七、责任 / 风险 / 验收

### 责任

| 角色 | 责任 |
| --- | --- |
| 后端 | 状态机 + QR |
| LLM | 简介 |
| 客户端 | UI |
| 合规 | grep 单测 |

### 风险

| ID | 风险 | 兜底 |
| --- | --- | --- |
| R-01 | QR 被泄露/转发 | token 不可猜 + 48h 失效 |
| R-02 | 通知未到 | App 内 badge 兜底 |
| R-03 | LLM 简介尴尬 | 用户必须编辑确认 |
| R-04 | 撤回时机 | cancelled 状态 + 通知 |

### AC

- [ ] AC-1 accepted 后才 contact_payload
- [ ] AC-2 grep 不泄露联系
- [ ] AC-3 48h 失效

---

## 八、附录

| 任务 | 关系 |
| --- | --- |
| P2-M13-03 匹配 | 来源 |
| P2-M13-05 隐私 | 弹窗前置 |
| P2-M13-06 风控 | 上限校验 |

---

## 九、变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-05-25 | 初版 |
