# P2-M8-09 · 教练侧无配额（AI 分析 / 对话不限）· 启动包（W29 起跑）

> 版本：v0.1（2026-05-25）
> 上游真源：[`docs/23 §4.9`](../23-二期可编码规格说明书.md#49-p2-m8-09--教练侧无配额ai-分析--对话不限)
> 前置：M8-02（角色切换）

---

## 一、文档目的与边界

为 **P2-M8-09** 落地 W29-W30 后端 SOP，让教练角色调用 AI 分析 / 对话不扣 quota，切回 user 仍按 user 计费。

### 边界（不做）

- 不修改 docs/22/23/02 字段
- 不实现教练独立计费模型（无配额 ≠ 永久免费，未来商业化时单独迭代）
- 不动一期 quota 表结构

---

## 二、现状盘点

### 2.1 一期能力

```
backend/app/services/quota_service.py
  → analysis_quotas / chat_quotas
  → check + decrement hook
```

### 2.2 缺口（vs docs/23 §4.9 FR）

- 没有 role 短路逻辑
- 没有教练行为分桶埋点
- 没有教练日调用上限风控

---

## 三、模块设计

### 3.1 改造

| 模块 | 路径 | 工程量 |
| --- | --- | --- |
| Role hook | `services/quota_service.py` 改 | 0.3 PW |
| 埋点分桶 | `services/analytics_service.py` 加 role 维度 | 0.2 PW |
| 风控阈值 | `services/abuse_detection.py`（新） | 0.3 PW |
| 单测 | tests | 0.2 PW |

**合计：~1 PW**

### 3.2 短路逻辑

```python
def check_and_decrement_quota(user_id: str, quota_type: str, request_role: str | None = None) -> bool:
    if request_role == 'coach' and is_active_coach(user_id):
        # 短路：教练角色不扣 quota
        emit_event('quota_skipped', user_id=user_id, role='coach', type=quota_type)
        return True
    # 一期既有逻辑
    return _check_and_decrement(user_id, quota_type)
```

### 3.3 角色来源

- 优先级 1：HTTP header `X-Role: coach`（前端切换 UI 时显式带）
- 优先级 2：JWT `role_claim='coach'`（M8-02 短 JWT 再签发后内嵌）
- 必校验：`coach_profiles.status='active'`，否则降级 user

### 3.4 风控阈值

```python
COACH_ANALYSIS_DAILY_LIMIT: int = 1000
COACH_CHAT_DAILY_LIMIT: int = 2000

# Redis 计数
key = f"coach_abuse:{user_id}:{date}:{quota_type}"
INCR + EXPIRE 86400
if count > limit: emit Sentry + 飞书告警 + 限流
```

### 3.5 埋点分桶

```python
emit_event('analysis_started', user_id=..., role='user' | 'coach', ...)
emit_event('chat_message', user_id=..., role='user' | 'coach', ...)
```

便于运营分析教练侧使用强度。

---

## 四、字段 v0.1

无 API 改动。

### 4.1 配置

```python
COACH_QUOTA_BYPASS_ENABLED: bool = True
COACH_ANALYSIS_DAILY_LIMIT: int = 1000
COACH_CHAT_DAILY_LIMIT: int = 2000
```

---

## 五、验证数据

- 单测：coach role → quota 不变（AC-1）
- 单测：切回 user → quota 扣减（AC-2）
- 模拟 1001 次/日 → Sentry 告警（AC-3）

---

## 六、W29-W30 周计划

| 周 | 任务 |
| --- | --- |
| W29 | role hook + 埋点 + 风控 |
| W30 | 灰度 5 教练 + 风控告警实测 |

---

## 七、责任 / 风险 / 验收

### 责任

| 角色 | 责任 |
| --- | --- |
| 后端 | hook + 风控 |
| 数据 | 埋点分桶 |

### 风险

| ID | 风险 | 兜底 |
| --- | --- | --- |
| R-01 | 教练身份伪造（直接发 X-Role） | 强制校验 `coach_profiles.status='active'`；否则降级 |
| R-02 | 教练号被盗用大量 AI 调用 | 日上限 1000 + 风控告警 + 强制 2FA |
| R-03 | 切角色漏配置 | role 默认 user；hook 默认走 user 配额 |
| R-04 | 教练量大成本失控 | 风控告警；可改成"教练日 quota=高额配额"而非无限 |

### AC

- [ ] AC-1 教练身份不扣 quota
- [ ] AC-2 切 user 后扣 quota
- [ ] AC-3 >1000/日告警

---

## 八、附录

| 任务 | 关系 |
| --- | --- |
| P2-M8-01 状态 | active 校验 |
| P2-M8-02 切换 | X-Role / JWT 来源 |

---

## 九、变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-05-25 | 初版；role 短路 + 风控 |
