# P2-M13-01 · 球友约球数据模型（5 张表）· 启动包（W22 起跑）

> 版本：v0.1（2026-05-25）
> 上游真源：[`docs/23 §9.1`](../23-二期可编码规格说明书.md#91-p2-m13-01--数据模型5-张表)
> 合规：[`docs/06 §13.4`](../06-数据安全与隐私合规文档.md)

---

## 一、文档目的与边界

为 **P2-M13-01** 落地 W22-W26 后端 SOP，建立 M13 5 张数据表（venues / meetup_invitations / meetup_feedbacks / self_organized_events / event_participations），**严格满足合规红线**。

### 边界（不做）

- 不修改 docs/22/23/06 字段
- 不开放任何用户可见 UI（M13-02 起）
- 不实现匹配 / 邀请逻辑（M13-03/04）

---

## 二、现状盘点

- 一期无任何 M13 相关表
- 一期 users.openid 不可与对方共享（合规）
- DEP-05 法律意见书在 Phase 2.3 上线前需到位

### 缺口

5 个 FR 全部新增；docs/03 §8.6 待 PR #20 合并后转正。

---

## 三、模块设计

### 3.1 新增

| 模块 | 路径 | 工程量 |
| --- | --- | --- |
| ORM models | `backend/app/models/meetup.py`（新） | 1 PW |
| Pydantic schemas | `backend/app/schemas/meetup.py`（新） | 0.5 PW |
| Migration 0023 | `0023_m13_venues_invitations.py`（docs/23 §9.1 标 0013-0014，实际 0023） | 0.3 PW |
| 反联系方式校验 | service 层 grep openid / 手机号 | 0.5 PW |
| 单测 | tests | 0.7 PW |

**合计：~3 PW**

### 3.2 5 张表

#### venues

```sql
CREATE TABLE venues (
    id VARCHAR(32) PRIMARY KEY,
    city VARCHAR(32) NOT NULL,
    name VARCHAR(128) NOT NULL,
    venue_type VARCHAR(20) NOT NULL,  -- indoor_range/outdoor_range/simulator_lounge/golf_course
    address TEXT,
    source VARCHAR(16) DEFAULT 'ugc',  -- ugc/verified
    status VARCHAR(16) DEFAULT 'active',  -- active/flagged/closed
    created_at TIMESTAMPTZ DEFAULT NOW(),
    INDEX idx_city_status (city, status)
);
```

#### meetup_invitations

```sql
CREATE TABLE meetup_invitations (
    id VARCHAR(32) PRIMARY KEY,
    inviter_user_id VARCHAR(32) NOT NULL REFERENCES users(id),
    invitee_user_id VARCHAR(32) NOT NULL REFERENCES users(id),
    venue_id VARCHAR(32) REFERENCES venues(id),
    proposed_time TIMESTAMPTZ,
    status VARCHAR(16) NOT NULL DEFAULT 'pending',  -- pending/accepted/declined/expired/cancelled
    contact_payload JSONB DEFAULT '{}',  -- 仅 status='accepted' 后写入
    risk_payload JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    INDEX idx_invitee_status (invitee_user_id, status),
    CONSTRAINT chk_no_self_invite CHECK (inviter_user_id != invitee_user_id)
);
```

#### meetup_feedbacks / self_organized_events / event_participations

详 docs/03 §8.6。

### 3.3 反联系方式硬约束

```python
def write_contact_payload(invitation, payload: dict):
    raw = json.dumps(payload)
    if re.search(r'1[3-9]\d{9}|openid|wx_[a-z0-9]+', raw):
        raise ComplianceError('contact_payload 含禁止字段')
    invitation.contact_payload = payload
```

PR 阻断：CI 加 grep 单测，含 `openid` / `手机号正则` 不通过。

---

## 四、字段 v0.1

无新 API（仅建表）。

```python
PHASE2_MEETUP_ENABLED: bool = False
```

---

## 五、验证数据

- §8.6 转正（AC-1）
- 5 表 + 索引 + 约束就位（AC-2）
- 反联系方式单测通过（AC-3）

---

## 六、W22-W26 周计划

| 周 | 任务 |
| --- | --- |
| W22 | schema 评审（含合规） |
| W23 | model + schema |
| W24 | migration 0023 |
| W25 | 反联系方式单测 |
| W26 | staging 验证 + AC |

---

## 七、责任 / 风险 / 验收

### 责任

| 角色 | 责任 |
| --- | --- |
| 后端 | 5 表 + ORM |
| 合规 | grep 单测 + DEP-05 推进 |

### 风险

| ID | 风险 | 兜底 |
| --- | --- | --- |
| R-01 | DEP-05 延期阻 Phase 2.3 | 法律意见书提前 1 个月签 |
| R-02 | openid 漏过 | CI grep + code review 双层 |
| R-03 | migration 编号冲突 | 待 head 确定后调整 |
| R-04 | UGC 滥用 venues | status='flagged' 隔离 |

### AC

- [ ] AC-1 §8.6 转正
- [ ] AC-2 5 表就位
- [ ] AC-3 反联系方式单测

---

## 八、附录

| 任务 | 关系 |
| --- | --- |
| P2-M13-02~10 | 数据基础 |
| P2-M9-05 | venues 消费 |
| DEP-05 | 法律意见书 |

---

## 九、变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-05-25 | 初版；5 表 + 合规硬约束 |
