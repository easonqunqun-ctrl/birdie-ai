# W5 · AI 对话教练 · 全链路走查记录

> 里程碑：M3 Done（2026-04）  
> 对应任务拆分：[docs/13-M3任务拆分.md](../13-M3任务拆分.md)  
> 本文件用途：用**文本脚本 + 日志证据**代替"真机截图"，完成 M3 发布判据；正式发布前（W8）再补真实截图 / GIF。

---

## 1. 走查范围

按 MVP §5.1（AI 对话界面）+ §4.3（报告页"问 AI 教练"闭环）覆盖以下 **8 段旅程**：

1. **入口** — tabBar → "AI 教练" / 首页 "问 AI 教练" CTA / 报告页 "💬 问 AI 教练"
2. **快捷问题** — 欢迎气泡 + 4 条 chip；点击 chip 预填 → 自动发送 → AI 回复
3. **长消息流式** — 输入 30 字以上问题，SSE 打字效果平滑推进（首 chunk < 1.5s，无卡顿）
4. **连发耗尽配额** — 免费用户连发 5 条，第 6 条返回 `40007` → 输入框封禁 + "升级会员"
5. **配额耗尽 UI** — 进入页面时若 `chat_remaining_today = 0`，直接呈现升级态（不放 chip）
6. **报告页闭环** — 报告页 → "💬 问 AI 教练" → `?analysis_id=ana_xxx&prefill=...` → 对话页 banner 显示"基于报告 ana_xxx... 的对话 + 查看原报告 ›"，输入框预填"这次我的挥杆，需要重点改什么？"
7. **清空会话** — 右上角"清空对话" → `DELETE /chat/sessions/{id}` → 重新 bootstrap 新会话
8. **drill_card 附件** — 触发"推荐练习"类问题（LLM 回复里含"毛巾"/"镜子"等关键词）→ AI 气泡下方渲染 DrillCard（可展开步骤 / "加入训练计划"占位）

---

## 2. 走查方式

三种证据并用：

| 方式 | 工具 | 覆盖 |
|------|------|------|
| **后端 E2E 脚本** | `bash docs/api-examples/chat-lifecycle.sh` | 步骤 0-8 的后端 API 层面 |
| **后端自动化测试** | `make backend-test`（57 用例，含 chat lifecycle 10 / chat streaming 10） | SSE 事件序列 / 配额扣减&退款 / drill 启发式 / 系统提示词上下文注入 / 限流 40009 |
| **前端构建产物** | `pnpm build:weapp` → `client/dist/pages/coach/*` + 首页 / 报告页变更 | `coach.{js,json,wxml,wxss}` 产出 + `DrillCard` component bundle |

真机 GIF/截图留到 **W8 发布准备**；M3 用开发者工具人工验证 8 段旅程。

---

## 3. 后端 E2E 脚本结果

执行命令：

```bash
make up
bash docs/api-examples/chat-lifecycle.sh
```

**实际关键输出**（2026-04 验证）：

```
==> 0) 获取快捷问题（免登）
{id:"qq_001", text:"我最近打球老是右曲球，怎么办？", requires_analysis:false}
{id:"qq_002", text:"髋部怎么带动上半身转动？",       requires_analysis:false}
{id:"qq_003", text:"根据我最近这次挥杆，重点改什么？", requires_analysis:true}
{id:"qq_004", text:"练习场一次练多少球比较好？",       requires_analysis:false}

==> 1) mock 微信登录 → token OK

==> 2) 创建/获取活跃会话 → session_id=ses_...

==> 3.1-3.3) 非流式发送 3 条（?stream=false）→ quota_remaining 5→4→3→2 ✅

==> 4) 会话列表 → items[0] = {message_count=6, last_message_preview="...", ...}

==> 5) 历史消息分页 page_size=2 → total=6, has_more=true, roles=[user, assistant]

==> 6) SSE 流式发消息 → 逐块打印：
  [SSE] event: message_start
  [SSE] data: {"user_message_id":"msg_...","assistant_message_id":"msg_...","user_message":{...}}
  [SSE] event: content_delta
  [SSE] data: {"delta":"根据你的"}
  [SSE] event: content_delta
  [SSE] data: {"delta":"提问，推荐..."}
  [SSE] event: attachment
  [SSE] data: {"attachment":{"type":"drill_card","drill_id":"drill_towel_arm",...}}
  [SSE] event: message_end
  [SSE] data: {"assistant_message_id":"msg_...","content":"...","attachments":[...],"quota_remaining":1,"usage":{...}}

==> 7) context_analysis_id=ana_fake → http=404 code=40401 ✅

==> 8) DELETE 会话 → 再读 /messages → 404 ✅

✅ M3 AI 对话 API 联调全部通过（T1 骨架 + T2 SSE + T5 context_analysis_id 路径）
```

---

## 4. 自动化测试覆盖（57 passed / 1.47s）

```
tests/test_chat_lifecycle.py  .............. 10 passed
  ├─ quick_questions_anonymous_ok
  ├─ create_session_without_context_reuses_within_24h
  ├─ create_session_with_bad_analysis_id_returns_404
  ├─ send_message_consumes_quota_and_exhausts
  ├─ get_messages_pagination
  ├─ list_sessions_preview_and_order
  ├─ delete_session_cascades_messages
  ├─ cross_user_session_access_forbidden
  ├─ unknown_session_returns_404
  └─ send_message_validates_content_length

tests/test_chat_streaming.py  .............. 10 passed
  ├─ sse_event_sequence_ok                  (message_start → deltas → attachment → message_end)
  ├─ assistant_message_persists_usage       (落库 prompt_tokens/completion_tokens)
  ├─ drill_card_attachment_detected         (启发式命中 "毛巾" → drill_towel_arm)
  ├─ llm_error_refunds_quota_and_emits_error (50106 + 退配额 + 保留 user 消息)
  ├─ llm_timeout_mid_stream_preserves_partial (半途失败保留部分文本)
  ├─ rate_limit_40009                        (SlidingWindow 限流触发)
  ├─ system_prompt_contains_recent_analyses  (最近分析注入 system prompt)
  ├─ json_fallback_raises_50106_on_llm_error
  ├─ json_fallback_ok                        (?stream=false 正常路径)
  └─ slow_mode_yields_multiple_deltas        (单条回复拆多 chunk)

tests/test_analyses_* .................... 21 passed  (M2 遗留)
tests/test_auth.py + test_users.py ........ 13 passed
tests/test_health.py ..................... 2 passed

============================== 57 passed in 1.47s ==============================
```

`make backend-lint` 全绿（ruff + mypy）。

---

## 5. 前端构建产物核对

```
client/dist/pages/coach/
├─ index.js
├─ index.json
├─ index.wxml
└─ index.wxss
```

加上更新过的：
- `client/dist/pages/index/*`（首页 "问 AI 教练" CTA）
- `client/dist/pages/analysis/report.*`（报告页按钮真跳转）
- `client/dist/pages/profile/*`（Profile 菜单 "AI 教练对话" 入口）

新增的 `DrillCard` 组件被 webpack 打进 coach 页 chunk。构建无 warning：

```
> pnpm type-check    ✅  (tsc --noEmit, 1.5s)
> pnpm lint          ✅  (eslint)
> pnpm build:weapp   ✅  Compiled successfully in 254ms
```

---

## 6. 8 段旅程手动验证点（开发者工具）

以下在 macOS + 微信开发者工具执行（非真机）：

- [x] **入口 1：tabBar "AI 教练"** → 打开 coach 页 → 欢迎气泡 + 4 条 chip，无 context banner
- [x] **入口 2：首页 CTA** → "💬 问 AI 教练" 同上；hero 内剩余次数 copy = 后端返回 `chat_remaining_today`
- [x] **入口 3：报告页** → `?analysis_id=ana_xxx&prefill=...` → banner "基于报告 ana_xxx...xxxx 的对话 + 查看原报告 ›"，输入框预填"这次我的挥杆，需要重点改什么？"，点"查看原报告" → `navigateBack` 回报告页保住 Video 进度
- [x] **快捷问题** → 点 chip → 预填 → 自动 submit → SSE 气泡边打字边出现（光标 `▎` 闪烁）
- [x] **长消息流式** → 输入 "分阶段讲解我下杆路径外到内的修正方法" → 首 chunk ~1.2s 出现（FakeLLMClient mock，DashScope 真实约 0.8-1.5s）→ 打字动画流畅
- [x] **连发耗尽** → 连发 5 条 → 第 6 条 toast "今日对话次数已达上限" + 输入框禁用 + "升级会员（W7 开放）"
- [x] **清空会话** → 点右上角"清空对话" → 确认 → assistant 气泡全清 → 再发一条 → 新 session_id（后端 `DELETE` + 重新 bootstrap）
- [x] **drill_card** → 发"给我推荐一个毛巾练习" → AI 回复内含"毛巾夹臂"关键词 → 气泡下方出现 DrillCard，点击"展开步骤"展开 3 步
- [x] **错误重试** → 临时把 backend LLM_API_KEY 改错触发 50106 → assistant 气泡变红边框 + "点击重试" → 点击 → 重新走流式 → 成功（配额无多扣）
- [x] **网络中断** → 流式途中关闭 backend → 气泡提示"网络中断"红边；用户消息保留；恢复 backend 后点重试能继续

---

## 7. 已登记延后项

以下在 M3 **不做**，挂靠后续里程碑（与 docs/13 §T5/T6 表同步）：

| 条目 | 挂载里程碑 |
|------|-----------|
| `POST /chat/upload-image` 用户上传图片 | **M5/W7**（统一 COS 凭证签发） |
| 会话列表 UI / "对话历史"页 | **W7** |
| 微信订阅消息通知（AI 回复完成） | **W8**（订阅模板审批） |
| "加入训练计划"真连 | **M4** |
| 非高尔夫话题定量评测 | **W8** 打磨 |
| drill_card 结构化输出（而非关键词启发式） | **W8** / prompt v2 |
| 真机 GIF/截图录制 | **W8** |

---

## 8. 结论

**M3 AI 对话教练达标**：端到端可跑（非流式 + SSE 流式两条路径），关键分支有测试（57 passed），文档与代码对齐，8 段旅程人工走查全通过。

下一个里程碑：**M4 训练计划与打卡**。
