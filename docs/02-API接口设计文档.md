# 「小鸟 AI」MVP API 接口设计文档

> 版本：v1.0  
> 日期：2026 年 4 月 14 日  
> 后端框架：Python FastAPI  
> 密级：内部机密

---

## 一、全局约定

### 1.1 基础信息

| 项目 | 值 |
|------|------|
| Base URL（开发） | `https://dev-api.xiaoniaoai.com/v1` |
| Base URL（生产） | `https://api.xiaoniaoai.com/v1` |
| 协议 | HTTPS（强制） |
| 数据格式 | JSON（Content-Type: application/json） |
| 字符编码 | UTF-8 |
| 时间格式 | ISO 8601（`2026-04-14T10:30:00+08:00`） |
| API 版本 | URL 路径版本控制（`/v1/`） |

### 1.2 认证方案

**JWT Bearer Token 认证**

```
Authorization: Bearer <jwt_token>
```

- Token 有效期：7 天
- Token 刷新：过期前 24 小时内可用旧 Token 换取新 Token
- 不需要认证的接口：登录、微信回调、健康检查

**JWT Payload 结构**：

```json
{
  "sub": "user_id",
  "openid": "wx_openid",
  "membership": "free|monthly|yearly|family",
  "iat": 1713081000,
  "exp": 1713685800
}
```

### 1.3 统一响应格式

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": { ... }
}
```

**分页响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [ ... ],
    "total": 100,
    "page": 1,
    "page_size": 20,
    "has_more": true
  }
}
```

**错误响应**：

```json
{
  "code": 40001,
  "message": "视频时长不符合要求",
  "detail": "视频时长为 2 秒，最低要求 3 秒",
  "request_id": "a1b2c3d4e5f67890"
}
```

其中 `request_id`（可选）与响应头 `X-Request-ID` 一致，便于对照服务端结构化日志排查。

### 1.4 错误码规范

| 错误码范围 | 类别 | 说明 |
|-----------|------|------|
| 0 | 成功 | 请求成功 |
| 40000-40099 | 参数错误 | 请求参数校验失败 |
| 40100-40199 | 认证错误 | Token 无效/过期/缺失 |
| 40300-40399 | 权限错误 | 无操作权限 |
| 40400-40499 | 资源错误 | 请求的资源不存在 |
| 42900-42999 | 限流错误 | 请求频率超限 |
| 50000-50099 | 服务端错误 | 系统内部错误 |
| 50100-50199 | AI 引擎错误 | AI 分析/对话服务异常 |
| 50200-50299 | 第三方服务错误 | 微信/支付/存储等外部服务异常 |

**详细错误码清单**：

| 错误码 | 消息 | 触发场景 |
|--------|------|----------|
| 40001 | 参数缺失 | 必填参数未传 |
| 40002 | 参数格式错误 | 参数类型/格式不正确 |
| 40003 | 视频格式不支持 | 非 MP4/MOV 格式 |
| 40004 | 视频时长不符 | < 3 秒或 > 30 秒 |
| 40005 | 文件过大 | 超过 100MB |
| 40006 | 分析次数不足 | 免费额度用完 |
| 40007 | 对话次数不足 | 每日对话限额用完（M3-T1） |
| 40009 | 操作过于频繁 | 对话发送等高频业务的速率限制（M3-T2 启用；40009 比 42901 更聚焦业务） |
| 40010 | 字段不允许修改 | 业务语义禁止（如 `onboarding_completed` 反向置 false） |
| 40011 | 上传凭证无效 | `upload_id` 不存在、已过期或不属于当前用户（M2-T1） |
| 40012 | 视频对象不存在 | 前端拿了凭证但未完成 POST 直传即调 `/analyses`（M2-T1） |
| 40092 | 分析进行中不可删除 | `pending` / `processing` 时调用 `DELETE /v1/analyses/{id}` |
| 40093 | 示例类型分析报告不可删除 | `swing_analyses.is_sample=true` 的记录 |
| 40101 | Token 缺失 | 未携带 Authorization 头 |
| 40102 | Token 无效 | Token 解析失败 |
| 40103 | Token 过期 | Token 已过期 |
| 40301 | 无会员权限 | 需要会员才能访问的功能 |
| 40401 | 用户不存在 | user_id 无对应记录 |
| 40402 | 分析记录不存在 | analysis_id 无对应记录 |
| 40403 | 训练计划不存在 | plan_id 无对应记录 |
| 40904 | 资源状态冲突 | 分析尚未完成却去取报告等状态冲突场景（M2-T1） |
| 42901 | 请求过于频繁 | 触发限流 |
| 50301 | 分析任务入队失败 | DB 已写入 `pending`，但 Celery/Redis broker 不可用导致无法调度（用户可稍后重试；运维可对单条 `ana_` 手工补偿 `run_swing_analysis.delay`） |
| 50001 | 服务内部错误 | 未预期的服务端异常 |
| 50100 | AI 引擎不可达 | Celery worker 连 AI 引擎超时/连接失败，耗尽 3 次重试后终态失败（backend 侧 transport 级失败，W6-T6 起启用） |
| 50101 | 视频预处理失败 | ffmpeg 解码失败 / 视频文件下载失败 / 转码异常（W6-T1 真实触发；对应 `ai_engine.PreprocessError`） |
| 50102 | 视频画质不足 | 拉普拉斯/clarity 硬门槛、低清晰度帧占比、极端抖动、综合 `quality_score`（W6-T1 + **v1.2.12 Batch-D** `POST /precheck` 早失败；对应 `ai_engine.PoorQualityError`） |
| 50103 | 未检测到人体 | MediaPipe 全帧未识别到人体，或有效帧占比 < 70%（W6-T1 真实触发；对应 `ai_engine.NoPersonError`） |
| 50104 | 未检测到挥杆 | 检测到人体但关键点序列不满足挥杆速度曲线特征（静止 / 走路 / 其它运动）（W6-T2 真实触发；对应 `ai_engine.NoSwingError`） |
| 50105 | AI 引擎内部异常 | MediaPipe 模型加载失败 / 推理异常（运维级问题，非用户可修复）（W6-T1 兜底触发；对应 `ai_engine.PoseModelError`） |
| 50106 | AI 对话服务异常 | LLM 服务不可用（M3-T2 启用；M2 时曾误写为 50105） |

> **50100 vs 50101-50105 的区分**：50100 是 backend → ai_engine 的 **transport 级**失败（HTTP 超时 / 连接错误，用户的视频可能完全没事，只是后端链路挂了）；50101-50105 是 ai_engine 返回的 **业务级**失败（视频本身有问题）。二者都会退回该次配额（`quota_refunded=true`）。

#### 1.3.1 AI Engine 内部 · `POST /precheck`（O-08，v1.2.12）

> **非 C 端 REST**：由 Celery `run_swing_analysis` 在调用 `POST /analyze` 前先请求 `{AI_ENGINE_URL}/precheck`。

| 字段 | 说明 |
|------|------|
| 请求体 | `{ "analysis_id": "ana_xxx", "video_url": "https://..." }` |
| 成功 | `{ "status": "passed", "quality_warnings": ["low_light", ...], "elapsed_ms": N, "scan_elapsed_ms": M }` — `scan_elapsed_ms` 为源视频采样扫描耗时（预算 ≤5s，不含网络下载） |
| 阻断 | `{ "status": "blocked", "error_code": 50102, "error_message": "..." }` — backend 直接落库 `failed` + 退配额，**不**再调 `/analyze` |
| mock | `AI_ENGINE_MOCK_MODE=true` 时恒返回 `passed` |

`quality_warnings` machine codes 与 §3.4 `quality_warnings` 列一致（含 v1.2.12 新增 `partial_occlusion` / `low_pose_confidence`）。
| 50201 | 微信服务异常 | 微信 API 调用失败 |
| 50202 | 支付服务异常 | 微信支付接口异常 |
| 50203 | 存储服务异常 | COS 上传/读取失败 |

### 1.4.1 微信小程序 · 分析完成订阅消息（服务端，非 REST）

| 项目 | 说明 |
|------|------|
| 触发时机 | Celery 分析任务 `_mark_completed` 事务提交成功后；**非** `is_sample` 记录 |
| 前置 | 用户于等待页已对模板发起 `wx.requestSubscribeMessage` 并接受；与下发使用同一 `template_id` |
| 配置 | `WECHAT_SUBSCRIBE_MESSAGE_ENABLED`、`WECHAT_SUBSCRIBE_ANALYSIS_TEMPLATE_ID`（须与客户端 `TARO_APP_SUBSCRIBE_TMPL_IDS` 首项一致）、`WECHAT_SUBSCRIBE_MINIPROGRAM_STATE`（`developer`/`trial`/`formal`） |
| 模板字段约定 | 下发 body 使用 **thing1**（标题短语）、**number2**（综合分）、**time3**（完成时间，东八区 `YYYY-MM-DD HH:mm`）；公众平台新建模板时需选用对应类型关键词，与代码一致 |
| 失败策略 | 微信返回拒绝/无次数等 **不** 影响分析报告落库；结构化日志 `subscribe_message.*` |

### 1.4.2 微信小程序 · 会员到期（惰性降级）订阅消息（服务端，非 REST）

| 项目 | 说明 |
|------|------|
| 触发时机 | `ensure_membership_valid` 判定 `membership_expires_at <= now` 并完成降级与 `flush` 之后；**非**定时「到期前 N 天」提醒 |
| 前置 | 用户于会员页已对模板发起 `wx.requestSubscribeMessage` 并接受；与下发使用同一 `template_id`（客户端 `TARO_APP_SUBSCRIBE_TMPL_IDS` **第二项**） |
| 配置 | 共用 `WECHAT_SUBSCRIBE_MESSAGE_ENABLED`、`WECHAT_SUBSCRIBE_MINIPROGRAM_STATE`；另需 `WECHAT_SUBSCRIBE_MEMBERSHIP_EXPIRE_TEMPLATE_ID` |
| 模板字段约定 | **thing1**（标题短语）、**time2**（到期时间，东八区 `YYYY-MM-DD HH:mm`）、**thing3**（行动短语）；与公众平台关键词类型一致 |
| 失败策略 | 仅记日志 `subscribe_message.*`，**不** 影响用户降级与配额修复 |

### 1.4.3 微信小程序 · 会员到期前 N 天提醒（Celery Beat，非 REST）

| 项目 | 说明 |
|------|------|
| 触发时机 | Celery Beat 任务 `xiaoniao.membership_pre_expiry_notify`（默认每日 **00:12** 上海时区日历）；当会员 `membership_expires_at` 与当日相差日历天数 ∈ **`MEMBERSHIP_PRE_EXPIRY_NOTIFY_DAYS`** 时下发（默认 **"3"**；多档 **"7,3,1"**） |
| 前置 | 用户于会员页已对 `wx.requestSubscribeMessage` **第三项**模板授权（`TARO_APP_SUBSCRIBE_TMPL_IDS` 逗号分隔第 3 个 ID）。多档 = 用户须分别授权多次才有多条配额 |
| 配置 | `WECHAT_SUBSCRIBE_MESSAGE_ENABLED`、`WECHAT_SUBSCRIBE_MEMBERSHIP_PRE_EXPIRE_TEMPLATE_ID`、`MEMBERSHIP_PRE_EXPIRY_NOTIFY_DAYS`（**csv** 列表；空 / "0" 关闭任务，最多 8 档防滥用）；部署栈须常驻 **celery beat**（与 `expire_stale_pending_orders` 同 `app/celery_app.py::beat_schedule`） |
| 去重 | Redis key `sub:preexpiry:{user_id}:{expire_date}:{days}`，45 天 TTL；每档独立去重 |
| 模板字段约定 | 与 §1.4.2 相同布局：**thing1**（「会员权益即将到期」）、**time2**（到期时间东八区）、**thing3**（行动短语） |
| 失败策略 | 单用户失败仅 `pre_expiry_notify_user_failed`（含 `days`）日志，不阻断批任务 |
| 配套：站内弹窗 | 客户端进入首页 / 会员中心若 `membership_expires_at - 今日 ∈ [1, 7]`，弹一次 modal 引导续费；用 `Storage` 按日期键去重；**不依赖订阅消息授权**，作为多档提醒的兜底通道 |

### 1.5 限流策略

| 接口类别 | 限流规则 |
|----------|----------|
| 通用接口 | 100 次/分钟/用户 |
| 视频上传 | 10 次/分钟/用户 |
| 挥杆分析 | 5 次/分钟/用户 |
| AI 对话 | 20 次/分钟/用户 |
| 登录接口 | 10 次/分钟/IP |

超过限流返回 HTTP 429 + 错误码 42901，响应头携带：

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1713081060
Retry-After: 30
```

---

## 二、用户模块（/users）

### 2.1 微信登录

```
POST /v1/auth/wechat-login
```

**无需认证**

**请求体**：

```json
{
  "code": "string（必填，wx.login 获取的临时 code）",
  "invite_code": "string（选填，邀请码）"
}
```

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "token": "eyJhbGciOiJIUzI1NiIs...",
    "expires_in": 604800,
    "is_new_user": true,
    "user": {
      "id": "usr_abc123",
      "nickname": "球友A",
      "avatar_url": "https://cos.xiaoniaoai.com/avatars/default.png",
      "golf_level": null,
      "membership_type": "free",
      "membership_expires_at": null,
      "created_at": "2026-04-14T10:30:00+08:00"
    }
  }
}
```

**处理逻辑**：

1. 用 code 调用微信 `code2session` 获取 openid
2. 查找已有用户 → 返回；新用户 → 创建记录
3. 如有 invite_code → 绑定邀请关系
4. 生成 JWT Token 返回

---

### 2.2 刷新 Token

```
POST /v1/auth/refresh-token
```

**需认证**（旧 Token 在过期前 24 小时可用）

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "token": "eyJhbGciOiJIUzI1NiIs...",
    "expires_in": 604800
  }
}
```

---

### 2.3 完成新用户引导

```
POST /v1/users/me/onboarding
```

**需认证**

**请求体**：

```json
{
  "golf_level": "beginner | elementary | intermediate | advanced",
  "primary_goals": ["distance", "accuracy", "short_game", "putting", "consistency"],
  "weekly_practice_frequency": "occasional | once | frequent | daily"
}
```

**校验规则**：

- `golf_level` 必填，枚举值
- `primary_goals` 必填，数组，至少 1 项，最多 5 项
- `weekly_practice_frequency` 必填，枚举值

**成功响应**：返回完整 `UserResponse`（结构同 2.4），其中 `stats` / `quota` 可能为 `null`（引导成功即可，统计/配额放在 GET /me 拉取）。

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": "usr_abc123",
    "nickname": "球友A",
    "avatar_url": "https://cos.xiaoniaoai.com/avatars/default.png",
    "golf_level": "beginner",
    "primary_goals": ["distance", "accuracy"],
    "weekly_practice_frequency": "frequent",
    "membership_type": "free",
    "membership_expires_at": null,
    "onboarding_completed": true,
    "stats": null,
    "quota": null,
    "created_at": "2026-04-01T10:30:00+08:00"
  }
}
```

---

### 2.4 获取当前用户信息

```
GET /v1/users/me
```

**需认证**

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": "usr_abc123",
    "nickname": "球友A",
    "avatar_url": "https://cos.xiaoniaoai.com/avatars/usr_abc123.jpg",
    "golf_level": "beginner",
    "primary_goals": ["distance", "accuracy"],
    "weekly_practice_frequency": "frequent",
    "membership_type": "free",
    "membership_expires_at": null,
    "is_member": false,
    "membership_days_remaining": 0,
    "has_completed_real_analysis": false,
    "onboarding_completed": true,
    "stats": {
      "total_analyses": 12,
      "total_practices": 28,
      "streak_days": 7,
      "best_score": 85,
      "score_improvement": 18
    },
    "quota": {
      "analysis_remaining": 2,
      "analysis_total": 3,
      "analysis_reset_at": "2026-05-01T00:00:00+08:00",
      "chat_remaining_today": 3,
      "chat_total_today": 5
    },
    "created_at": "2026-04-01T10:30:00+08:00"
  }
}
```

---

### 2.5 更新用户信息

```
PATCH /v1/users/me
```

**需认证**

**请求体**（所有字段均为选填，只传需要修改的）：

```json
{
  "nickname": "string（2-12 个字符）",
  "avatar_url": "string（头像 URL）",
  "golf_level": "beginner | elementary | intermediate | advanced",
  "primary_goals": ["distance", "accuracy"],
  "weekly_practice_frequency": "occasional | once | frequent | daily",
  "onboarding_completed": true
}
```

**字段语义**：

- 仅对"入传字段"进行修改（后端按 `exclude_unset` 处理），未传入的字段保持原值。
- `onboarding_completed` 仅允许从 `false` 置为 `true`（首启页"跳过"入口）；**不允许**通过本接口反向置 `false`，否则返回错误码 `40010`。

**成功响应**：返回更新后的完整用户对象（同 2.4）。

---

### 2.6 提交意见反馈

```
POST /v1/feedback
```

**需认证**

**请求体**：

```json
{
  "content": "string（必填，1-500 字）",
  "contact": "string（选填，联系方式）"
}
```

**成功响应**：

```json
{
  "code": 0,
  "message": "感谢你的反馈",
  "data": {
    "feedback_id": "fb_xyz789"
  }
}
```

---

### 2.7 申请账号注销

```
POST /v1/users/me/delete-request
```

**需认证**

**请求体**：

```json
{
  "reason": "string（选填，注销原因）",
  "confirmation": "DELETE（必填，需用户输入 DELETE 确认）"
}
```

**处理逻辑**：

1. 校验 `confirmation` 字段必须为 "DELETE"
2. 检查用户是否有未完成的订单（如有，拒绝注销）
3. 创建注销申请，进入 7 天冷静期
4. 冷静期内用户可随时登录取消注销
5. 7 天后自动执行注销：软删除用户数据、清除视频文件、匿名化分析数据

**成功响应**：

```json
{
  "code": 0,
  "message": "注销申请已提交",
  "data": {
    "delete_scheduled_at": "2026-04-21T10:30:00+08:00",
    "cancel_before": "2026-04-21T10:30:00+08:00",
    "message": "你的账号将在 7 天后注销。期间你可以随时登录取消。"
  }
}
```

---

### 2.8 取消账号注销

```
POST /v1/users/me/cancel-delete
```

**需认证**（仅在冷静期内有效）

**成功响应**：

```json
{
  "code": 0,
  "message": "注销申请已取消",
  "data": {
    "status": "active"
  }
}
```

---

## 三、挥杆分析模块（/analyses）

### 3.1 获取视频上传凭证

```
POST /v1/analyses/upload-token
```

**需认证**

**请求体**：

```json
{
  "file_name": "string（原始文件名）",
  "file_size": 52428800,
  "file_type": "video/mp4 | video/quicktime",
  "duration": 8.5
}
```

**校验逻辑**：

1. 检查用户分析配额（免费用户检查剩余次数）
2. 校验文件大小 ≤ 100MB
3. 校验文件类型为 MP4/MOV
4. 校验时长 3-30 秒
5. 生成 COS 临时上传凭证

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "upload_id": "upl_abc123",
    "cos_config": {
      "bucket": "birdie-videos-1300000000",
      "region": "ap-shanghai",
      "key": "uploads/2026/04/14/usr_abc123/upl_abc123.mp4",
      "credentials": {
        "tmp_secret_id": "...",
        "tmp_secret_key": "...",
        "session_token": "...",
        "expired_time": 1713084600
      }
    }
  }
}
```

---

### 3.1a 经 API 上报视频（微信小程序推荐）

```
POST /v1/analyses/uploads/{upload_id}/video
```

**需认证**（`Authorization: Bearer …`，与 `/upload-token` 同一用户）

**Content-Type**：`multipart/form-data`，表单字段 **`file`**（视频二进制）。

**前置**：已成功调用 `POST /v1/analyses/upload-token`，路径参数 **`upload_id`** 与响应中一致。

**行为概要**：

1. 校验 Redis 上传凭证归属当前用户；
2. 写入对象存储（MinIO / COS），并把 Redis 中的 **`file_size`** 更新为实际上传字节数，以便 **`POST /v1/analyses`** 与对象大小校验一致；
3. 客户端继续调用 **`POST /v1/analyses`** 创建任务。

**说明**：与接口同源，适合微信小程序 **`wx.uploadFile`**；可避免直连存储网关时的 502 / 超时。RN 或自建工具若仍需预签名直传，可使用 `upload-token` 返回的 `upload_url`。

**小程序客户端策略（实现见 `client/src/services/analysisService.ts`）**：对 **502/503/504**、网关不可用文案、超时及常见连接类 `uploadFile:fail`，默认 **至多 3 次**间隔重试；**401/403（含过期签名语义）及 HTTP 404（缺同源接口）** 不重试同款请求体，其中 **403/ExpiredSignature** 须 **重新** `upload-token` 后再传（`analysis/params` 对已识别错误做一轮刷新）。

**成功响应**：统一信封，`code=0`，`data` 可为 `null`。

---

### 3.2 创建挥杆分析任务

```
POST /v1/analyses
```

**需认证**

**请求体**：

```json
{
  "upload_id": "upl_abc123（必填，上传凭证 ID）",
  "camera_angle": "face_on | down_the_line（必填）",
  "club_type": "driver | fairway_wood | iron_3 | iron_4 | iron_5 | iron_6 | iron_7 | iron_8 | iron_9 | wedge | putter | unknown（必填）"
}
```

**处理逻辑**：

1. 验证 upload_id 有效且视频已上传至 COS
2. 扣减用户分析配额
3. 创建分析记录（状态 `pending`）
4. 将分析任务推入消息队列（会员用户进优先队列）
5. 返回分析 ID

**成功响应**：

```json
{
  "code": 0,
  "message": "分析任务已创建",
  "data": {
    "analysis_id": "ana_def456",
    "status": "pending",
    "queue_position": 3,
    "estimated_seconds": 25,
    "created_at": "2026-04-14T10:35:00+08:00"
  }
}
```

---

### 3.3 查询分析状态

```
GET /v1/analyses/{analysis_id}/status
```

**需认证**（仅查看自己的分析）

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "analysis_id": "ana_def456",
    "status": "analyzing",
    "stage": "pose_estimating | phase_segmenting | scoring | diagnosing | generating | completed | failed",
    "stage_progress": 60,
    "estimated_remaining_seconds": 12,
    "error": null
  }
}
```

**状态枚举**：

| status | stage | 说明 |
|--------|-------|------|
| pending | — | 排队等待 |
| processing | preprocessing | 视频预处理 |
| processing | pose_estimating | 姿态估计 |
| processing | phase_segmenting | 挥杆阶段分割 |
| processing | scoring | 动作评分 |
| processing | diagnosing | 问题诊断 |
| processing | generating | 生成报告 |
| completed | — | 分析完成 |
| failed | — | 分析失败 |

**失败时的 error 字段**：

```json
{
  "error": {
    "code": 50103,
    "message": "视频中未检测到完整人物，请确保全身入镜",
    "quota_refunded": true
  }
}
```

---

### 3.4 获取分析报告详情

```
GET /v1/analyses/{analysis_id}
```

**需认证**

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": "ana_def456",
    "user_id": "usr_abc123",
    "status": "completed",
    "camera_angle": "down_the_line",
    "club_type": "iron_7",
    "video_url": "https://cos.xiaoniaoai.com/videos/ana_def456/original.mp4",
    "skeleton_video_url": "https://cos.xiaoniaoai.com/videos/ana_def456/skeleton.mp4",

    "overall_score": 78,
    "score_change": 3,
    "score_level": "good",
    "quality_warnings": [],

    "phase_scores": {
      "setup": { "score": 82, "label": "站位准备" },
      "backswing": { "score": 74, "label": "上杆轨迹" },
      "top": { "score": 80, "label": "顶点位置" },
      "downswing": { "score": 65, "label": "下杆转换", "is_weakest": true },
      "impact": { "score": 79, "label": "击球触球" },
      "follow_through": { "score": 85, "label": "收杆平衡" }
    },

    "issues": [
      {
        "type": "casting",
        "name": "抛杆（Casting）",
        "severity": "high",
        "description": "你的手腕在下杆初期就开始释放，导致击球时杆面打开，容易产生右曲球。这是目前最需要改善的环节。",
        "key_frame_url": "https://cos.xiaoniaoai.com/videos/ana_def456/frames/casting.jpg",
        "key_frame_timestamp": 1.8
      },
      {
        "type": "bent_left_arm",
        "name": "上杆左臂弯曲",
        "severity": "medium",
        "description": "上杆至顶点时左臂弯曲约 15°，影响挥杆弧度的一致性。",
        "key_frame_url": "https://cos.xiaoniaoai.com/videos/ana_def456/frames/bent_arm.jpg",
        "key_frame_timestamp": 1.2
      }
    ],

    "recommendations": [
      {
        "drill_id": "drill_towel_arm",
        "name": "毛巾夹臂练习",
        "target_issue": "casting",
        "description": "修复下杆时过早释放手腕",
        "duration_minutes": 15,
        "sets": 3,
        "steps": [
          "取一条小毛巾，折叠后夹在双臂之间（肘关节内侧）",
          "做半挥杆练习，保持毛巾不掉落",
          "感受双臂与身体的连接感",
          "逐渐加大挥杆幅度",
          "每组做 10 次挥杆，共 3 组"
        ]
      }
    ],

    "phase_timestamps": {
      "setup": { "start": 0.0, "end": 0.8 },
      "backswing": { "start": 0.8, "end": 1.5 },
      "top": { "start": 1.5, "end": 1.7 },
      "downswing": { "start": 1.7, "end": 2.0 },
      "impact": { "start": 2.0, "end": 2.1 },
      "follow_through": { "start": 2.1, "end": 2.8 }
    },

    "skeleton_data_url": "https://cos.xiaoniaoai.com/videos/ana_def456/skeleton.json",
    "share_card_url": null,
    "analyzed_at": "2026-04-14T10:35:25+08:00",
    "created_at": "2026-04-14T10:35:00+08:00"
  }
}
```

**字段补充**：

- **`quality_warnings`**：`string[]`，AI 引擎返回的**非阻断**拍摄质量提示（machine codes，如 `low_light`、`camera_shake`），入库列 `swing_analyses.quality_warnings`（JSONB）。与失败态 `error` 互斥存在；空数组表示无附加提示。客户端展示文案见 `client/src/constants/qualityWarnings.ts`，产品与话术真源见 [`docs/20` §4.3～§4.4](./20-AI引擎产品力迭代设计.md)。

---

### 3.4d 匹配最相似职业球手镜头（M12-04 · 灰度 `PHASE2_PROS_ENABLED`）

```
GET /v1/analyses/{analysis_id}/pro-matches?limit=5&record=true
```

**需认证**（仅本人 **`completed`** 且非 `is_sample` 的分析）

**Query**：

| 参数 | 默认 | 说明 |
|------|------|------|
| `limit` | `5` | 返回 Top-N，范围 1–10 |
| `record` | `true` | 是否将 Top-1 写入 `user_pro_match_history` |

**守门**：

- `PHASE2_PROS_ENABLED=false` → **404**（`40406`）
- `pending` / `processing` / 无 `overall_score` → **400**（`40001`）
- `is_sample=true` → **400**（`40093`，与软删除守门一致）

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "analysis_id": "ana_xxx",
    "matches": [
      {
        "match_score": 87.5,
        "match_details": {
          "camera_angle_match": true,
          "base_score": 72.5,
          "components": { "overall": 85.0, "phase_proxy": 78.0 }
        },
        "clip": { "id": "psc_xxx", "club_type": "iron_7", "camera_angle": "face_on", "...": "..." },
        "player": { "id": "pp_xxx", "name": "Demo Pro · 内置示例", "...": "..." }
      }
    ],
    "recorded_match_id": "upmh_xxx"
  }
}
```

**匹配逻辑（v0.1 启发式）**：同 `club_type` 硬过滤 → `overall_score` / `phase_scores` 相似度加权 → 机位一致 +15 分。客户端 service：`prosService.matchForAnalysis()`。

**UI（M12-05）**：报告页展示 Top-1 匹配卡片 → `pages/analysis/pro-compare?id={analysis_id}&clipId={clip_id}`（并排双视频 + 双序列雷达叠加 + 六维分差表）。预览匹配时建议 `record=false`，进入对比页时再写历史（可选）。

---

### 3.4a 软删除分析报告

```
DELETE /v1/analyses/{analysis_id}
```

**需认证**（仅删除本人记录）

**语义**：

- 默认 **软删除**：写入 `swing_analyses.deleted_at`，**不**物理删对象存储。
- `pending` / `processing`：**不允许删除**，返回 **40092**。
- `is_sample=true`（若存在入库样本记录）：**不允许删除**，返回 **40093**。
- 重复删除：**幂等**，返回成功。
- 删除后：`GET /v1/analyses` 列表、`GET /v1/analyses/{id}` 详情、`GET /v1/analyses/{id}/public` 公开报告均视为不存在（列表不出现，详情与公开接口 **404**，错误码 **40402**）；用户当周训练计划中若 `source_analysis_id` / 任务的 `verification_analysis_id` 指向该分析，会在服务端清空对应外键。

**成功响应**：`code=0`，`data=null`。

---

### 3.4b 生成分享用小程序码（对象存储缓存）

```
POST /v1/analyses/{analysis_id}/share-card
```

**需认证**（仅本人 **`completed`** 且未软删的分析；`sample` 不允许）

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "wxa_code_url": "https://…/share/wxa/ana_xxx.png"
  }
}
```

小程序码 **scene** 为 `i={analysis_id}`（≤32 字符），落地页 **`pages/analysis/report`** 须在 `onLoad` 从 `options.scene` 解析该参数（与首页扫码进入一致）。

---

### 3.4c 获取公开（脱敏）分析报告

```
GET /v1/analyses/{analysis_id}/public
```

**无需认证**。被分享者从分享卡片进入时使用；`is_sample` / 未完成 / 已软删 / 不存在 → **404**（**40402**）。

**成功响应** `data` 字段与 `PublicReport` 对齐，除 `overall_score`、问题摘要外，还包含与 §3.4 同源的 **`quality_warnings`**（字符串数组，machine codes，可为 `[]`）。**不包含** 原视频与骨骼视频 URL、`phase_scores`、`recommendations`、`user_id` 等。

---

### 3.5 获取分析历史列表

```
GET /v1/analyses?page=1&page_size=20
```

**需认证**

**查询参数**：

| 参数 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| page | int | 否 | 1 | 页码 |
| page_size | int | 否 | 20 | 每页数量，最大 50 |
| club_type | string | 否 | — | 按球杆类型筛选 |
| date_from | string | 否 | — | 起始日期（ISO 8601） |
| date_to | string | 否 | — | 截止日期 |

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "id": "ana_def456",
        "camera_angle": "down_the_line",
        "club_type": "iron_7",
        "overall_score": 78,
        "score_change": 3,
        "thumbnail_url": "https://cos.xiaoniaoai.com/videos/ana_def456/thumb.jpg",
        "status": "completed",
        "analyzed_at": "2026-04-14T10:35:25+08:00"
      }
    ],
    "total": 12,
    "page": 1,
    "page_size": 20,
    "has_more": false
  }
}
```

---

### 3.6 获取示例分析报告（体验入口）

```
GET /v1/analyses/sample
```

**不需认证**（允许匿名访问，已登录用户带 Token 也会被静默识别，便于埋点但不做权限控制）

**来源**：MVP §3.6「用示例视频先体验一下」。新用户在真正上传视频之前可以先看一份固定的演示报告，了解 AI 能给出什么样的诊断价值。

**行为约束**：
- **完全固定**：每次返回**完全一致**的数据（便于运营 / QA 做截图与自动化对比）。
- **不入库**：不创建 `swing_analyses` 记录，也不会出现在 `GET /v1/analyses` 列表中。
- **不计配额**：即使带 Token 访问，`user.quota.analysis_remaining` 不会变化。
- **固定 id**：返回体 `id == "sample"`，前端报告页以此识别"示例模式"（可展示"这是演示"徽章、禁用/隐藏"再拍一段"以外的部分交互）。

**请求**：无 body、无 query、无需 path 参数。

**响应** — 200：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "id": "sample",
    "user_id": "sample",
    "status": "completed",
    "camera_angle": "face_on",
    "club_type": "iron_7",
    "video_url": "https://xiaoniao-assets.oss-cn-hangzhou.aliyuncs.com/samples/swing_demo.mp4",
    "video_duration": 2.8,
    "skeleton_video_url": "https://xiaoniao-assets.oss-cn-hangzhou.aliyuncs.com/samples/swing_demo.mp4",
    "thumbnail_url": "https://xiaoniao-assets.oss-cn-hangzhou.aliyuncs.com/samples/swing_demo_thumb.jpg",
    "overall_score": 78,
    "score_level": "good",
    "phase_scores": {
      "setup":         {"score": 85, "label": "站位准备", "is_weakest": false},
      "backswing":     {"score": 78, "label": "上杆轨迹", "is_weakest": false},
      "top":           {"score": 80, "label": "顶点位置", "is_weakest": false},
      "downswing":     {"score": 72, "label": "下杆转换", "is_weakest": true},
      "impact":        {"score": 78, "label": "击球触球", "is_weakest": false},
      "follow_through":{"score": 82, "label": "收杆平衡", "is_weakest": false}
    },
    "phase_timestamps": {
      "setup":         {"start": 0.0, "end": 0.8},
      "backswing":     {"start": 0.8, "end": 1.5},
      "top":           {"start": 1.5, "end": 1.7},
      "downswing":     {"start": 1.7, "end": 2.0},
      "impact":        {"start": 2.0, "end": 2.1},
      "follow_through":{"start": 2.1, "end": 2.8}
    },
    "issues": [
      {"type": "casting", "name": "抛杆（Casting）", "severity": "high", "description": "...", "key_frame_timestamp": 1.8, "key_frame_url": null},
      {"type": "early_extension", "name": "提前伸展（Early Extension）", "severity": "medium", "description": "...", "key_frame_timestamp": 1.9, "key_frame_url": null}
    ],
    "recommendations": [
      {"drill_id": "drill_towel_arm", "target_issue": "casting", "sort_order": 0},
      {"drill_id": "drill_hip_rotation", "target_issue": "early_extension", "sort_order": 1}
    ],
    "quality_warnings": ["low_light"],
    "share_card_url": null,
    "analyzed_at": "2026-04-01T10:00:03Z",
    "created_at": "2026-04-01T10:00:00Z"
  }
}
```

**实现说明**：数据源是 `backend/app/services/sample_fixture.py::build_sample_report()`，与 `ai_engine/app/sample_fixture.py::build_sample_analyze_result()` **保持同源**（改数值时两边都要改）。不走 AI 引擎 HTTP 调用，TTFB ≤ 100ms。

---

### 3.7 生成分享卡片

**与 §3.4b 为同一路径**：`POST /v1/analyses/{analysis_id}/share-card`。契约与示例见 **§3.4b**（响应仅含 `wxa_code_url`）。

本节保留为目录锚点；早期设计稿中的 `share_card_url` / `mini_program_path` **未落地**。

---

## 四、AI 对话模块（/chat）

### 4.1 创建/获取对话会话

```
POST /v1/chat/sessions
```

**需认证**

**请求体**：

```json
{
  "context_analysis_id": "ana_def456（选填，关联分析报告 ID）"
}
```

**逻辑说明**：

- 如有未过期的活跃会话（24 小时内有消息），返回该会话
- 如无活跃会话，创建新会话
- 如传入 `context_analysis_id`，将该分析结果注入会话上下文

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "session_id": "chat_ghi789",
    "messages": [
      {
        "role": "assistant",
        "content": "你好！我是你的 AI 高尔夫教练小鸟。随时可以问我挥杆技术、练习方法或高尔夫知识方面的问题。",
        "timestamp": "2026-04-14T10:40:00+08:00"
      }
    ],
    "context_analysis_id": "ana_def456",
    "created_at": "2026-04-14T10:40:00+08:00"
  }
}
```

---

### 4.2 发送消息（流式）

```
POST /v1/chat/sessions/{session_id}/messages
```

**需认证**

**请求体**：

```json
{
  "content": "string（必填，1-500 字）",
  "attachments": [
    {
      "type": "image",
      "url": "https://cos.xiaoniaoai.com/chat/usr_abc123/img001.jpg"
    }
  ]
}
```

**P-02 话题边界（v1.2.9+）**：服务端在扣减对话配额前对用户输入做轻量分类。命中 **非高尔夫 / 医疗伤病 / 赌球博彩** 时，直接返回固定引导文案（同步 JSON 或 SSE 单帧 `content_delta`），**不调用 LLM、不消耗当日对话配额**。高尔夫相关问题仍走 LLM + 配额扣减。

**响应方式**：Server-Sent Events（SSE）

- **默认流式**：`Accept: text/event-stream`（或不带 `Accept`）→ 下述 SSE 序列
- **非流式降级**：URL 追加 `?stream=false` → 普通 JSON `{code, data: {user_message, assistant_message, quota_remaining}}`，供低端机 / 单元测试使用（M3-T1）

```
Content-Type: text/event-stream

event: message_start
data: {"user_message_id": "msg_user_001", "assistant_message_id": "msg_asst_001", "user_message": {"id":"msg_user_001","session_id":"ses_xx","role":"user","content":"我的右曲球怎么办","created_at":"2026-04-14T12:00:00+00:00"}}

event: content_delta
data: {"delta": "根据你最近"}

event: content_delta
data: {"delta": "3 次挥杆分析，"}

event: content_delta
data: {"delta": "你的右曲球主要有两个原因：\n\n1. 下杆路径偏外..."}

event: attachment
data: {"attachment": {"type": "drill_card", "drill_id": "drill_towel_arm", "name": "毛巾夹臂练习", "description": "修复下杆时过早释放手腕", "duration_minutes": 15, "steps": [...]}}

event: message_end
data: {"assistant_message_id": "msg_asst_001", "content": "根据你最近 3 次挥杆分析...", "attachments": [...], "quota_remaining": 4, "usage": {"prompt_tokens": 1200, "completion_tokens": 350}}
```

**SSE 事件类型**（与后端 `chat_service.generate_stream_events` 实现一致）：

| 事件 | data 字段 | 说明 |
|------|----------|------|
| `message_start` | `user_message_id`, `assistant_message_id`, `user_message{...}` | 回复开始，后端已把用户消息落库并扣减配额，同时**预留** assistant 消息 id（尚未落库）；前端据此替换乐观气泡 id |
| `content_delta` | `delta` | 文本增量，按 LLM token-level 推送 |
| `attachment` | `attachment{type,drill_id,name,...}` 或 `video_card{drill_id,title}` | `drill_card` / `video_card` 由后端启发式关键字触发（`_detect_reply_attachments`）；`analysis_card` 由 LLM/后续结构化输出 |
| `message_end` | `assistant_message_id`, `content`（完整文本）, `attachments[]`, `quota_remaining`（-1 表示无限）, `usage{prompt_tokens, completion_tokens}` | 回复结束，assistant 消息已落库 |
| `error` | `code`（`50106`）, `message`（用户可见）, `detail`（排查用） | 生成过程出错；后端已退还本轮配额，但 `message_start` 之前落库的 user 消息保留（前端可保留气泡） |

**配额行为**：

- 进 `message_start` 之前后端已 `quota.consume(1)` 且 commit → 即使 SSE 传输中断，配额也算扣减
- LLM 异常（触发 `error` 事件）时，后端 `_finalize_llm_error` 会 `quota.refund(1)` + 保留 user 消息 + 若有 partial 文本则把 `partial + "\n\n[回复中断，请稍后重试]"` 作为 assistant 消息落库（无 partial 就只落 user 消息）
- 因 `error` 事件本身**不携带** `quota_remaining`（只有 `code / message / detail`），前端收到 `error` 后建议用 `GET /users/me` 重拉配额快照

---

### 4.3 获取对话历史

```
GET /v1/chat/sessions/{session_id}/messages?page=1&page_size=50
```

**需认证**

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "id": "msg_001",
        "role": "assistant",
        "content": "你好！我是你的 AI 高尔夫教练小鸟...",
        "attachments": [],
        "timestamp": "2026-04-14T10:40:00+08:00"
      },
      {
        "id": "msg_002",
        "role": "user",
        "content": "我总是打出右曲球怎么办？",
        "attachments": [],
        "timestamp": "2026-04-14T10:40:15+08:00"
      },
      {
        "id": "msg_003",
        "role": "assistant",
        "content": "根据你最近 3 次挥杆分析...",
        "attachments": [
          {
            "type": "drill_card",
            "drill_id": "drill_towel_arm",
            "name": "毛巾夹臂练习"
          }
        ],
        "timestamp": "2026-04-14T10:40:18+08:00"
      }
    ],
    "total": 3,
    "page": 1,
    "page_size": 50,
    "has_more": false
  }
}
```

---

### 4.4 获取会话列表

```
GET /v1/chat/sessions?page=1&page_size=20
```

**需认证**

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "id": "chat_ghi789",
        "last_message": "根据你最近 3 次挥杆分析...",
        "last_message_at": "2026-04-14T10:40:18+08:00",
        "message_count": 6,
        "created_at": "2026-04-14T10:40:00+08:00"
      }
    ],
    "total": 5,
    "page": 1,
    "page_size": 20,
    "has_more": false
  }
}
```

---

### 4.5 上传对话图片（**W7 延后**）

> **M3 实现状态**：**未实现，延后到 W7**。当前 `chat/messages` SSE 支持 `attachments[].image` 结构在响应侧呈现（drill_card 同理），但**用户上传图片链路**（小程序 chooseImage → 后端 COS 临时 key → `image_url` 回填消息）要和 W7 "会员付费凭证上传"一起做，统一 COS 凭证签发逻辑，避免重复实现。

```
POST /v1/chat/upload-image
```

**需认证**

**请求方式**：`multipart/form-data`

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| file | File | 是 | 图片文件，支持 JPG/PNG/WEBP |
| max size | — | — | 单张最大 5MB |

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "image_url": "https://cos.xiaoniaoai.com/chat/usr_abc123/img_20260414_001.jpg",
    "width": 750,
    "height": 1000
  }
}
```

**说明**：上传成功后将 `image_url` 作为消息附件的 `url` 字段传入发送消息接口。

---

### 4.6 获取快捷问题列表

```
GET /v1/chat/quick-questions
```

**需认证**

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "questions": [
      {
        "id": "qq_001",
        "text": "我的挥杆有什么问题？",
        "requires_analysis": true
      },
      {
        "id": "qq_002",
        "text": "推荐今天练什么",
        "requires_analysis": false
      },
      {
        "id": "qq_003",
        "text": "怎么打好沙坑球？",
        "requires_analysis": false
      },
      {
        "id": "qq_004",
        "text": "上杆时身体怎么转？",
        "requires_analysis": false
      }
    ]
  }
}
```

**说明**：`requires_analysis` 为 true 时，需要用户至少有 1 次挥杆分析记录，否则点击后提示"请先完成一次挥杆分析"。

---

### 4.7 清空/删除会话

```
DELETE /v1/chat/sessions/{session_id}
```

**需认证**

**成功响应**：

```json
{
  "code": 0,
  "message": "对话已清空"
}
```

---

## 五、训练模块（/training）

### 5.1 获取当前训练计划

```
GET /v1/training/plans/current
```

**需认证**

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": "plan_mno345",
    "week_start": "2026-04-14",
    "week_end": "2026-04-20",
    "total_tasks": 5,
    "completed_tasks": 2,
    "ai_summary": "重点关注下杆时手腕释放时机，这是你目前最大的改善空间",
    "tasks": [
      {
        "id": "task_001",
        "drill_id": "drill_towel_arm",
        "name": "毛巾夹臂练习",
        "target_issue": "抛杆",
        "scheduled_date": "2026-04-14",
        "duration_minutes": 15,
        "sets": 3,
        "difficulty": "medium",
        "status": "completed",
        "completed_at": "2026-04-14T18:30:00+08:00",
        "verification_analysis_id": null
      },
      {
        "id": "task_002",
        "drill_id": "drill_half_swing",
        "name": "半挥杆节奏练习",
        "target_issue": "挥杆节奏",
        "scheduled_date": "2026-04-16",
        "duration_minutes": 20,
        "sets": 5,
        "difficulty": "easy",
        "status": "pending",
        "completed_at": null,
        "verification_analysis_id": null
      }
    ],
    "created_at": "2026-04-14T10:36:00+08:00"
  }
}
```

---

### 5.2 获取练习详情

```
GET /v1/training/drills/{drill_id}
```

**需认证**

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": "drill_towel_arm",
    "name": "毛巾夹臂练习",
    "target_issues": ["casting"],
    "description": "通过在双臂间夹住毛巾进行挥杆练习，建立双臂与身体的连接感，纠正下杆时过早释放手腕的问题。",
    "steps": [
      "取一条小毛巾，折叠后夹在双臂之间（肘关节内侧）",
      "做半挥杆练习，保持毛巾不掉落",
      "感受双臂与身体的连接感",
      "逐渐加大挥杆幅度",
      "每组做 10 次挥杆，共 3 组"
    ],
    "duration_minutes": 15,
    "sets": 3,
    "difficulty": "medium",
    "illustration_url": "https://cos.xiaoniaoai.com/drills/towel_arm/demo.gif",
    "video_url": "https://cos.xiaoniaoai.com/drills/towel_arm/demo.mp4",
    "tips": [
      "如果毛巾反复掉落，可以先用更小幅度的挥杆练习",
      "保持正常呼吸节奏，不要因为怕掉毛巾而过于紧张"
    ]
  }
}
```

---

### 5.3 完成训练任务（打卡）

```
POST /v1/training/tasks/{task_id}/complete
```

**需认证**

**请求体**：

```json
{
  "verification_analysis_id": "ana_xxx（选填，拍视频验证后的分析 ID）"
}
```

**成功响应**：

```json
{
  "code": 0,
  "message": "训练完成，继续加油！",
  "data": {
    "task_id": "task_001",
    "status": "completed",
    "completed_at": "2026-04-14T18:30:00+08:00",
    "streak_days": 8,
    "streak_milestone": null,
    "plan_progress": {
      "completed": 3,
      "total": 5
    }
  }
}
```

**streak_milestone**（里程碑，非空时前端展示成就弹窗）：

```json
{
  "streak_milestone": {
    "type": "streak_7",
    "title": "连续打卡 7 天",
    "description": "坚持就是进步，你太棒了！"
  }
}
```

---

### 5.4 获取进步曲线数据

```
GET /v1/training/progress?period=30d
```

**需认证 + 需会员**

**查询参数**：

| 参数 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| period | string | 否 | 30d | 时间范围：7d / 30d / 90d / all |
| dimension | string | 否 | overall | 维度：overall / setup / backswing / top / downswing / impact / follow_through |

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "dimension": "overall",
    "period": "30d",
    "data_points": [
      { "date": "2026-03-15", "score": 60, "analysis_id": "ana_001" },
      { "date": "2026-03-20", "score": 65, "analysis_id": "ana_002" },
      { "date": "2026-03-28", "score": 72, "analysis_id": "ana_003" },
      { "date": "2026-04-05", "score": 75, "analysis_id": "ana_004" },
      { "date": "2026-04-14", "score": 78, "analysis_id": "ana_005" }
    ],
    "summary": {
      "start_score": 60,
      "current_score": 78,
      "improvement": 18,
      "total_analyses": 12,
      "total_practices": 28,
      "max_streak_days": 12,
      "most_improved_dimension": {
        "name": "downswing",
        "label": "下杆转换",
        "improvement": 22
      }
    }
  }
}
```

---

### 5.4.1 用户进步曲线数据源（已实现 · `/users/me`）

```
GET /v1/users/me/analysis-progress?window_days=90
```

**需认证 + 仅统计正式分析**（`is_sample=false`、已完成、未软删、`overall_score` 非空）

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| window_days | int | 否 | 仅取最近 N 日历天内的点；不传或 `0` 表示不按天截断（仍受服务端 `max_points` 上限，默认 500） |

**响应**：`data.points[]`，元素为 `analysis_id` + `analyzed_at` + `overall_score` + `phase_scores`（可选，六维扁平 map，如 `{ "setup": 82, "backswing": 75, ... }`；时间升序）。

---

### 5.5 获取打卡日历

```
GET /v1/training/calendar?month=2026-04
```

**需认证**

**查询参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| month | string | 是 | 年月，格式 YYYY-MM |

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "month": "2026-04",
    "days": [
      { "date": "2026-04-01", "practiced": true, "tasks_completed": 2, "analysis_done": false },
      { "date": "2026-04-02", "practiced": true, "tasks_completed": 1, "analysis_done": true },
      { "date": "2026-04-03", "practiced": false, "tasks_completed": 0, "analysis_done": false }
    ],
    "monthly_stats": {
      "practice_days": 12,
      "total_tasks_completed": 18,
      "total_analyses": 5,
      "current_streak": 7
    }
  }
}
```

---

## 5A、课程模块（/courses · M11，灰度 `PHASE2_COURSES_ENABLED`）

> 读端点见 M11-02；考核见 M11-04。以下 M11-05 证书/勋章。

### 5A.1 当前学习阶段与证书列表

```
GET /v1/users/me/course-stage
GET /v1/users/me/certificates
GET /v1/users/me/certificates/{cert_id}
```

**需认证**；未启用课程灰度时返回 `40406`。

**course-stage 响应字段**：`current_stage`（1–7）、`earned_stages[]`、`certificates[]`（含 `course_title` / `badge_label` / `holder_name` / `stage_title`，供客户端 Canvas 合成证书图）。

### 5A.2 考核升阶返回证书

`POST /v1/lessons/{lesson_id}/attempt` 成功且触发升阶时，响应新增可选字段 `certificate`（结构同 `CertificateDetailRead`）。

### 5A.3 教练定制课程（M11-06）

```
GET    /v1/users/me/coach/courses
POST   /v1/users/me/coach/courses
PATCH  /v1/users/me/coach/courses/{course_id}
POST   /v1/users/me/coach/courses/{course_id}/lessons
POST   /v1/users/me/coach/courses/{course_id}/publish
POST   /v1/users/me/coach/courses/{course_id}/unpublish
```

**需认证** + 课程灰度开启；写端点额外要求用户 ID 在服务端 `COACH_COURSE_USER_IDS` 白名单（M8 教练认证就位前）。创建的课程 `created_by_user_id` 指向教练；发布后出现在公开 `GET /v1/courses` 列表。

---

## 5B、球手对比库（/pros · M12，灰度 `PHASE2_PROS_ENABLED`）

> 读端点：`GET /v1/pros`、`GET /v1/pros/{player_id}`、`GET /v1/pros/{player_id}/clips`（M12-02）；匹配见 §3.4d（M12-04）。

### 5B.1 当前每周精选（M12-06）

```
GET /v1/pros/topics/current
```

**无需登录**；`PHASE2_PROS_ENABLED=false` → **404**（`40406`）。

**语义**：返回 `is_published=true` 且 `week_starts_at` 为空或 ≤ 今日的专题中，按 `week_starts_at` / `published_at` 最新一条；`clips[]` 展开为 `{ clip, player }`（仅已发布镜头 + 在架球手）。无专题时 **`data=null`**（200，非 404）。

**客户端**：`prosService.currentTopic()`；`pages/pros/index` 顶部 banner → `pages/pros/topic` 详情。

### 5B.2 镜头 PGC 解说与 AI 解读（M12-07）

```
GET  /v1/pros/clips/{clip_id}/annotations
POST /v1/pros/clips/{clip_id}/pgc-insight
```

**annotations**：**无需登录**；`PHASE2_PROS_ENABLED=false` → **404**（`40406`）。返回该镜头已发布且 `is_visible=true` 的解说列表（`annotation_type`：`text` / `voice` / `sketch`），按 `time_marker_ms` 升序。

**pgc-insight**：**需 JWT**；同上灰度门控。请求体可选 `{ "analysis_id": "ana_xxx" }`，用于把用户分析报告摘要带入 LLM prompt；无 `analysis_id` 时仅基于镜头 PGC 与特征快照生成对比提示。响应 `{ clip_id, insight }`（Markdown 纯文本）。

**客户端**：`prosService.annotations()` / `prosService.pgcInsight()`；`pages/pros/detail` 镜头卡片「解说」→ `pages/pros/clip-insight`；职业对比页可带 `analysisId` query。

---

## 六、支付模块（/payments）

### 6.1 创建订阅订单

```
POST /v1/payments/subscriptions
```

**需认证**

**请求体**：

```json
{
  "plan_type": "monthly | yearly | family（必填）"
}
```

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "order_id": "ord_pqr678",
    "plan_type": "yearly",
    "amount": 29900,
    "currency": "CNY",
    "wechat_pay_params": {
      "timeStamp": "1713081000",
      "nonceStr": "abc123xyz",
      "package": "prepay_id=wx14103...",
      "signType": "RSA",
      "paySign": "..."
    }
  }
}
```

前端拿到 `wechat_pay_params` 后调用 `wx.requestPayment(params)` 唤起微信支付。

---

### 6.2 支付结果回调（微信通知后端）

```
POST /v1/payments/wechat/notify
```

**微信服务器调用，非前端接口**

处理逻辑：
1. 验证微信签名
2. 更新订单状态为已支付
3. 更新用户会员类型和到期时间
4. 记录支付流水

---

### 6.2.1 生产：申请全额退款（用户 JWT）

```
POST /v1/payments/orders/{order_id}/apply-refund
```

**需认证**。仅在 **`WECHAT_PAY_MOCK_MODE=false`** 可用；mock 演练请用 `mock-refund`。

- 可选 query `reason`。
- MVP：支付成功后 **`PAYMENT_SELF_REFUND_WINDOW_HOURS`（默认 24）小时内**可申请自助退款；超限返回 `40094`。
- 成功后本地订单 **仍为 `paid`**；以异步 **`POST /v1/payments/wechat/refund-notify`** 为终态。
- 响应 `data.wechat`：`/v3/refund/domestic/refunds` JSON 摘要；`data.order`：当前本地订单。

**商户平台退款 notify_url**：填写 **`WECHAT_PAY_REFUND_NOTIFY_URL`**；若留空，则尝试从 `WECHAT_PAY_NOTIFY_URL` 将路径 `.../payments/wechat/notify` 替换为 **`.../payments/wechat/refund-notify`**。

---

### 6.2.2 退款结果异步通知（微信）

```
POST /v1/payments/wechat/refund-notify
```

**微信服务器调用，非前端接口**

`refund_status=SUCCESS` 且金额与订单一致时：订单 **`refunded`**、写 **`payment_transactions`（`transaction_type=refund`）**、会员降级（与 mock 退款对齐的 MVP 策略）。

---

### 6.2.3 自动续费 / 委托代扣（Q-B5）

```
POST /v1/payments/auto-renew
```

**需认证**。请求体：`{"enabled": true|false}`。

- **`WECHAT_PAY_MOCK_MODE=true`**：`enabled=true` 时直接 `users.auto_renew=true`；关闭时 `auto_renew=false`。
- **真实模式**：关闭时直接 `auto_renew=false`；**开启**时调用微信 **`/v3/papay/scheduled-deduct-sign/contracts/pre-entrust-sign/mini-program`**，响应：

```json
{
  "auto_renew": false,
  "papay_sign": {
    "pre_entrustweb_id": "…",
    "redirect_appid": "wxbd687630cd02ce1d",
    "redirect_path": "pages/PwdExemptContract/index"
  }
}
```

客户端使用 `wx.navigateToMiniProgram` 跳转，并将 **`pre_entrustweb_id`** 拼入 `redirect_path` 的 query（字段名以微信文档为准）。签约成功后微信回调：

```
POST /v1/payments/wechat/papay-notify
```

配置 **`WECHAT_PAY_PAPAY_PLAN_ID`**、**`WECHAT_PAY_PAPAY_NOTIFY_URL`（HTTPS）**；服务端尝试与支付回调一致的 V3 `resource` 解密，失败则按平文 JSON 解析。成功后写入 **`users.papay_contract_id`** 且 **`auto_renew=true`**。

**`GET /v1/users/me/membership`** 增加字段 **`papay_contract_id`**（可空）。

---

### 6.3 查询订单状态

```
GET /v1/payments/orders/{order_id}
```

**需认证**

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "order_id": "ord_pqr678",
    "plan_type": "yearly",
    "amount": 29900,
    "status": "paid | pending | failed | refunded",
    "paid_at": "2026-04-14T10:38:00+08:00",
    "membership_expires_at": "2027-04-14T10:38:00+08:00"
  }
}
```

---

### 6.4 获取会员信息

```
GET /v1/payments/membership
```

**需认证**

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "membership_type": "yearly",
    "started_at": "2026-04-14T10:38:00+08:00",
    "expires_at": "2027-04-14T10:38:00+08:00",
    "auto_renew": true,
    "days_remaining": 365,
    "payment_history": [
      {
        "order_id": "ord_pqr678",
        "plan_type": "yearly",
        "amount": 29900,
        "paid_at": "2026-04-14T10:38:00+08:00"
      }
    ]
  }
}
```

---

### 6.5 取消自动续费

```
POST /v1/payments/membership/cancel-auto-renew
```

**需认证**

**成功响应**：

```json
{
  "code": 0,
  "message": "已关闭自动续费，当前会员有效期至 2027-04-14",
  "data": {
    "auto_renew": false,
    "expires_at": "2027-04-14T10:38:00+08:00"
  }
}
```

---

### 6.6 Mock 演练：超时关单 / mock 退款

**实际路由（已实现）对齐 `POST /v1/payments/orders`（非历史文档中的 `/subscriptions`）见 §10.**

#### 待支付超时关单（运维 / 调度）

- 服务层：`payment_service.expire_stale_pending_orders` 将 **`pending`** 且 **`created_at`** 早于 `now - PAYMENT_PENDING_ORDER_EXPIRE_MINUTES` 的订单批量置为 **`cancelled`**（默认阈值 **120** 分钟，`.env`: `PAYMENT_PENDING_ORDER_EXPIRE_MINUTES`）。
- Celery：`xiaoniao.expire_stale_pending_orders`，在 `celery_app.beat_schedule` 中默认为 **每 15 分钟**触发；**须在部署栈中常驻 `celery beat`**（或等价 cron 调 Celery `-A app.celery_app call xiaoniao.expire_stale_pending_orders`），否则仅靠配置不会生效。

```
（无前端入口；按需由调度器触发同名 Celery task）
```

#### Mock 全额退款（仅 `WECHAT_PAY_MOCK_MODE=true`）

```
POST /v1/payments/orders/{order_id}/mock-refund?reason=<可选>
```

**需认证**；语义：对已 **`paid`** 订单记账 **`refunded`**、写 **`payment_transactions`** 类型 **`refund`**，并将会员降级回 **free**（与生产「微信退款 + 退款回调」链路尚未对接；本接口服务于联调 / 冒烟）。

---

### 6.7 微信小程序虚拟支付（xpay，iOS 合规）

> 详单与运维步骤见 [`docs/release-notes/wechat-xpay-runbook.md`](../release-notes/wechat-xpay-runbook.md)。

**开关**：`WECHAT_XPAY_ENABLED=true` 且 `WECHAT_PAY_MOCK_MODE=false` 时，小程序 **不再** 走 JSAPI `wx.requestPayment`，改走 `wx.requestVirtualPayment`（道具直购 `short_series_goods`）。

#### 创建订单（扩展）

```
POST /v1/payments/orders
```

**请求体**（在原有 `plan_type` 基础上）：

```json
{
  "plan_type": "monthly | yearly",
  "wx_login_code": "wx.login() 临时 code（虚拟支付必填）"
}
```

**成功响应 `data.prepay_params`（virtual）**：

```json
{
  "mock": false,
  "payment_method": "virtual",
  "sign_data": "{\"offerId\":\"…\",\"buyQuantity\":1,\"env\":0,\"currencyType\":\"CNY\",\"productId\":\"…\",\"goodsPrice\":3900,\"outTradeNo\":\"ord_…\",\"attach\":\"monthly\"}",
  "pay_sig": "…",
  "signature": "…",
  "mode": "short_series_goods"
}
```

前端调用：

```javascript
wx.requestVirtualPayment({
  signData: prepay_params.sign_data,
  paySig: prepay_params.pay_sig,
  signature: prepay_params.signature,
  mode: 'short_series_goods',
})
```

`data.virtual_pay_enabled=true` 表示当前服务端已启用虚拟支付。

#### 发货推送（微信 → 后端）

```
POST /v1/wechat/mp-push
```

**微信服务器调用**（小程序后台 **开发管理 → 消息推送** 配置 URL）。  
Event=`xpay_goods_deliver_notify` 时：验签 → 按 `OutTradeNo` 激活会员 → 响应 `{"ErrCode":0,"ErrMsg":"success"}`。

#### 查单补偿（客户端）

```
POST /v1/payments/orders/{order_id}/sync-from-wechat
```

虚拟支付模式下改为调用微信 `/xpay/query_order`；订单 `status ∈ {2,3,4}` 时执行与发货推送相同的到账逻辑。

#### 自动续费限制

`WECHAT_XPAY_ENABLED=true` 时 **`POST /v1/payments/auto-renew` 开启** 返回 `40098`（委托代扣与 iOS 虚拟支付规则不兼容，须手动续费）。

---

## 七、邀请裂变模块（/invitations）

### 7.1 获取邀请信息

```
GET /v1/invitations/me
```

**需认证**

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "invite_code": "BRD9X2",
    "invite_url": "https://mp.weixin.qq.com/s?...",
    "mini_program_path": "pages/index?invite=BRD9X2",
    "stats": {
      "total_invited": 8,
      "valid_invited": 6,
      "bonus_analyses_earned": 6,
      "bonus_membership_days_earned": 7
    },
    "rewards": [
      { "threshold": 5, "reward": "7天会员", "achieved": true },
      { "threshold": 10, "reward": "15天会员", "achieved": false, "progress": "6/10" }
    ]
  }
}
```

---

### 7.2 获取邀请记录

```
GET /v1/invitations/records?page=1&page_size=20
```

**需认证**

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "invitee_nickname": "球***A",
        "invitee_avatar": "https://...",
        "status": "valid",
        "bonus_type": "analysis",
        "bonus_amount": 1,
        "invited_at": "2026-04-13T15:00:00+08:00"
      }
    ],
    "total": 6,
    "page": 1,
    "page_size": 20,
    "has_more": false
  }
}
```

---

### 7.3 记录分享行为

```
POST /v1/invitations/share-action
```

**需认证**

**请求体**：

```json
{
  "share_type": "report | invite_poster | moments",
  "target_id": "ana_def456（report 类型时必填）"
}
```

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "bonus_granted": true,
    "bonus_type": "analysis",
    "bonus_amount": 1,
    "message": "分享成功，获得 1 次免费分析"
  }
}
```

---

## 八、通用模块

### 8.1 获取首页数据（聚合接口）

```
GET /v1/home
```

**需认证**

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "user_brief": {
      "nickname": "球友A",
      "avatar_url": "...",
      "membership_type": "free",
      "analysis_remaining": 2,
      "analysis_total": 3
    },
    "recent_analyses": [
      {
        "id": "ana_def456",
        "club_type": "iron_7",
        "overall_score": 78,
        "score_change": 3,
        "thumbnail_url": "...",
        "analyzed_at": "2026-04-14T10:35:25+08:00"
      }
    ],
    "today_drill": {
      "drill_id": "drill_towel_arm",
      "name": "毛巾夹臂练习",
      "target_issue": "抛杆",
      "duration_minutes": 15,
      "task_id": "task_001"
    },
    "daily_tip": {
      "content": "练球前的 5 分钟热身，可以让你的挥杆更稳定。",
      "tip_id": "tip_042"
    },
    "unread_notifications": 2
  }
}
```

---

### 8.2 获取通知列表

```
GET /v1/notifications?page=1&page_size=20
```

**需认证**

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "id": "notif_001",
        "type": "analysis_complete",
        "title": "挥杆分析完成",
        "content": "你的挥杆分析已完成，评分 78 分",
        "target_type": "analysis",
        "target_id": "ana_def456",
        "read": false,
        "created_at": "2026-04-14T10:35:25+08:00"
      }
    ],
    "total": 15,
    "page": 1,
    "page_size": 20,
    "has_more": false,
    "unread_count": 2
  }
}
```

---

### 8.3 标记通知已读

```
POST /v1/notifications/read
```

**需认证**

**请求体**：

```json
{
  "notification_ids": ["notif_001", "notif_002"],
  "read_all": false
}
```

---

### 8.4 健康检查

```
GET /v1/health
```

**无需认证**

**成功响应**（HTTP 200；`status` 为 `degraded` 时表示子依赖异常，仍返回 200 便于编排探活）：

```json
{
  "status": "ok",
  "version": "1.0.0",
  "env": "local",
  "timestamp": "2026-04-14T10:00:00+08:00",
  "services": {
    "backend": "ok",
    "database": "ok",
    "redis": "ok",
    "ai_engine": "ok"
  },
  "ai_engine": {
    "reachable": true,
    "mock_mode": false,
    "warning": null
  }
}
```

字段说明：

- `services.ai_engine`：`ok` 表示 HTTP 探针成功且（`env` 为 `staging`/`prod` 时）引擎**未**处于 Mock；若为 `degraded: mock_mode=true`，说明线上仍误开 `AI_ENGINE_MOCK_MODE`，骨骼/衍生视频将不符合真实 MediaPipe 输出。
- `ai_engine.mock_mode`：透传引擎 `GET {AI_ENGINE_URL}/health` 的 `mock_mode`，便于与后端配置交叉核对。

---

### 8.5 数据埋点上报

```
POST /v1/events
```

**需认证**

**请求体**：

```json
{
  "events": [
    {
      "event_name": "report_view",
      "params": {
        "analysis_id": "ana_def456",
        "source": "home_list"
      },
      "timestamp": "2026-04-14T10:36:00+08:00"
    }
  ]
}
```

**成功响应**：

```json
{
  "code": 0,
  "message": "success"
}
```

---

## 九、接口汇总表

| # | 方法 | 路径 | 认证 | 说明 |
|---|------|------|------|------|
| 1 | POST | /v1/auth/wechat-login | 否 | 微信登录 |
| 2 | POST | /v1/auth/refresh-token | 是 | 刷新 Token |
| 3 | POST | /v1/users/me/onboarding | 是 | 完成引导 |
| 4 | GET | /v1/users/me | 是 | 获取用户信息 |
| 5 | PATCH | /v1/users/me | 是 | 更新用户信息 |
| 6 | POST | /v1/feedback | 是 | 提交反馈 |
| 7 | POST | /v1/users/me/delete-request | 是 | 申请账号注销 |
| 8 | POST | /v1/users/me/cancel-delete | 是 | 取消账号注销 |
| 9 | POST | /v1/analyses/upload-token | 是 | 获取上传凭证 |
| 9a | POST | /v1/analyses/uploads/{upload_id}/video | 是 | 经 API 上报视频（multipart `file`，小程序推荐） |
| 10 | POST | /v1/analyses | 是 | 创建分析任务 |
| 11 | GET | /v1/analyses/{id}/status | 是 | 查询分析状态 |
| 12 | GET | /v1/analyses/{id} | 是 | 获取分析报告 |
| 12b | GET | /v1/analyses/{id}/pro-matches | 是 | 匹配最相似职业镜头（M12-04，`PHASE2_PROS_ENABLED`） |
| 12a | DELETE | /v1/analyses/{id} | 是 | 软删除分析报告（进行中/示例不可删） |
| 13 | GET | /v1/analyses | 是 | 分析历史列表 |
| 14 | GET | /v1/analyses/sample | 否 | 获取示例分析报告（免登体验，固定数据） |
| 15 | POST | /v1/analyses/{id}/share-card | 是 | 生成分享卡片 |
| 15 | POST | /v1/chat/sessions | 是 | 创建/获取会话（M3-T1 ✅） |
| 16 | POST | /v1/chat/sessions/{id}/messages | 是 | 发送消息（SSE，M3-T2 ✅；`?stream=false` 非流式降级同端点，M3-T1 ✅） |
| 17 | GET | /v1/chat/sessions/{id}/messages | 是 | 获取对话历史（M3-T1 ✅） |
| 18 | GET | /v1/chat/sessions | 是 | 获取会话列表（M3-T1 ✅，UI 挂 W7） |
| 19 | POST | /v1/chat/upload-image | 是 | 上传对话图片（**挂 W7**，M3 不做） |
| 20 | GET | /v1/chat/quick-questions | 是 | 获取快捷问题列表（M3-T1 ✅） |
| 21 | DELETE | /v1/chat/sessions/{id} | 是 | 删除会话（M3-T1 ✅） |
| 22 | GET | /v1/training/plans/current | 是 | 获取当前训练计划 |
| 23 | GET | /v1/training/drills/{id} | 是 | 获取练习详情 |
| 24 | POST | /v1/training/tasks/{id}/complete | 是 | 完成训练打卡 |
| 25 | GET | /v1/training/progress | 是 | 获取进步曲线 |
| 26 | GET | /v1/training/calendar | 是 | 获取打卡日历 |
| 27 | POST | /v1/payments/subscriptions | 是 | 创建订阅订单 |
| 28 | POST | /v1/payments/wechat/notify | 否 | 微信支付回调（商户平台 notify_url 须与此路径一致） |
| 28a | POST | /v1/payments/wechat/refund-notify | 否 | 退款结果异步通知（验签解密，见 §6.2.2） |
| 29 | GET | /v1/payments/orders/{id} | 是 | 查询订单状态 |
| 29a | POST | /v1/payments/orders/{id}/apply-refund | 是 | **生产**：向微信发起全额退款（见 §6.2.1） |
| 29b | POST | /v1/payments/orders/{id}/mock-refund | 是 | Mock：`paid`→`refunded` + 降级会员（详见 §6.6） |
| 30 | GET | /v1/payments/membership | 是 | 获取会员信息 |
| 31 | POST | /v1/payments/membership/cancel-auto-renew | 是 | 取消自动续费 |
| 32 | GET | /v1/invitations/me | 是 | 获取邀请信息 |
| 33 | GET | /v1/invitations/records | 是 | 获取邀请记录 |
| 34 | POST | /v1/invitations/share-action | 是 | 记录分享行为 |
| 35 | GET | /v1/home | 是 | 首页聚合数据 |
| 36 | GET | /v1/notifications | 是 | 获取通知列表 |
| 37 | POST | /v1/notifications/read | 是 | 标记通知已读 |
| 38 | GET | /v1/health | 否 | 健康检查 |
| 39 | POST | /v1/events | 是 | 数据埋点上报 |

---

## 十、W7 实现偏差说明（2026-04 · 商业化与社交）

> 设计阶段的接口形态（§五-§七）与 W7 实际落地存在以下路径/语义差异。**代码以本节为准**。路径差异不是 bug，而是为了让 `/users/me/*` 这一套集中聚合的路由前缀更一致（W1 开始的约定）。

### 10.1 支付接口（原 §六 → 实际 §十）

| 设计稿（§六） | W7 实际路径 | 备注 |
|---|---|---|
| `POST /v1/payments/subscriptions` | `POST /v1/payments/orders` | 请求体仍为 `{plan_type}`；返回 `{order_id, prepay_params}`，mock 模式下 `prepay_params = {"mock": true}` |
| `POST /v1/payments/wechat-notify`（旧稿路径） | `POST /v1/payments/wechat/notify` | 已实现；环境变量 `WECHAT_PAY_NOTIFY_URL` 须配公网 HTTPS，例如 `https://api.example.com/v1/payments/wechat/notify`。mock 模式下回调返回 FAIL |
| `GET /v1/payments/orders/{id}` | `GET /v1/payments/orders/{id}` | ✅ 无变化 |
| `GET /v1/payments/membership` | `GET /v1/users/me/membership` | 返回 `is_member, membership_type, expires_at, days_remaining, auto_renew, papay_contract_id`；`GET /v1/users/me` 另含 `is_member` / `membership_days_remaining` / `has_completed_real_analysis` 等派生字段 |
| `GET /v1/payments/plans` | `GET /v1/payments/plans` | **新增**：开通页套餐列表 |
| `GET /v1/me/orders` | `GET /v1/users/me/orders` | 我的订单列表，按 `created_at DESC` |
| `POST /v1/payments/membership/cancel-auto-renew` | （**W8 落地**） | 依赖真实支付委托扣款签约，W7 暂不支持 |
| —— | `POST /v1/payments/orders/{id}/mock-refund`（**mock**） | 演练：`paid→refunded` + 降级会员 |
| —— | `POST /v1/payments/orders/{id}/apply-refund` + `POST …/refund-notify` | **生产**：申请退款（§6.2.1）+ 异步结案（§6.2.2）；需 `WECHAT_PAY_NOTIFY_URL`/退款回调与商户平台一致 |
| —— | Celery **`xiaoniao.expire_stale_pending_orders`** | **pending→cancelled**：默认 > `PAYMENT_PENDING_ORDER_EXPIRE_MINUTES`；需 **`celery beat`** 或小周期等价调度 |

### 10.2 训练接口（原 §五 → 实际路径）

| 设计稿（§五） | W7 实际路径 | 备注 |
|---|---|---|
| `GET /v1/training/plans/current` | `GET /v1/users/me/training-plan/current` | 对齐 `/users/me/*` 聚合前缀；响应结构无变化 |
| `POST /v1/training/tasks/{id}/complete` | `POST /v1/training-plan/tasks/{id}/complete` | 幂等：重复完成直接返回"已完成"；响应带 `current_streak_days` 供客户端即时刷新 |
| `GET /v1/training/drills/{id}` | `GET /v1/drills`（列表） | W7 只提供列表；单条详情暂由客户端 `constants/drillLibrary.ts` 离线提供 |
| `GET /v1/training/progress` | （**W8 落地**） | 依赖周/月聚合 UI；数据源 `practice_logs` 已采集 |
| `GET /v1/training/calendar` | `GET /v1/users/me/practice-logs?month=YYYY-MM` | 月度练习记录；返回每天一条聚合（completed_count + duration_total） |

### 10.3 邀请裂变接口（原 §七 → 实际路径）

| 设计稿（§七） | W7 实际路径 | 备注 |
|---|---|---|
| `GET /v1/invitations/me` | `GET /v1/users/me/invite-info` | 返回 `{invite_code, total_invited, valid_count, next_reward_at, days_to_next_reward, total_bonus_days}`；`invite_url`（带小程序码）延后 W8 |
| `GET /v1/invitations/records` | `GET /v1/users/me/invitations` | invitee 昵称经脱敏（"张***丰"），预防信息泄露 |
| `POST /v1/invitations/share-action` | `POST /v1/shares/log`（见下） | 合并到统一的分享埋点接口 |

### 10.4 分享接口（原 §三 §七 → 实际 `/shares/*`）

| 设计稿 | W7 实际路径 | 备注 |
|---|---|---|
| `POST /v1/analyses/{id}/share-card`（§3.4b） | `POST /v1/analyses/{id}/share-card` | **已实现**：服务端生成 `wxa_code_url`（小程序码 PNG，scene `i=`…，对象存储缓存）。**未实现**：离屏 Canvas 整图合成海报（若后续需要单独 `share_card_url`，可列为增强项，非当前契约） |
| —— | `POST /v1/shares/log` | **新增**。请求体 `{share_type: 'report'\|'invite_poster'\|'moments', target_id?}`；W7 只用 `report`；不做业务校验只埋点 |
| —— | `GET /v1/analyses/{id}/public` | **新增 · 无需登录**。被分享者访问的脱敏报告；对 `is_sample`/未完成/不存在 → 404；返回 `overall_score` + 最多 3 条 `high/medium` 问题名 + **`quality_warnings`**；**不含**骨骼视频/训练建议/key_frame_url/user_id |

### 10.5 `UserResponse` 扩展字段（W7）

```jsonc
{
  // ... W2 既有字段 ...
  "membership_type": "monthly",             // free/monthly/yearly/family
  "membership_expires_at": "2026-05-21T...",
  "is_member": true,                         // 派生：membership_type!='free' && now()<expires_at
  "membership_days_remaining": 29,           // 派生：max(0, (expires_at - now()).days)
  "has_completed_real_analysis": true,      // 派生：至少一条非示例且 status=completed 的分析
  "stats": {
    "total_analyses": 12,
    "streak_days": 4,                        // W7-T3：current_streak_days
    "best_score": 82
  }
}
```

### 10.6 错误码新增

| 码 | 触发 | 源 |
|---|---|---|
| 40006 | 分析配额已用完（免费 3 次/月） | `quota_service.py`（M1 既有；W7 复用，会员命中则跳过） |
| 40402 | 分享的报告不存在/已删除/未完成/是示例 | `services/share_service.py::get_public_report` |
| 40013 | 订单状态不允许本次操作（已支付重复 confirm / 已取消再支付等） | `services/payment_service.py::PaymentNotAllowedError` |

---

*文档完*
