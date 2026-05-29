# Phase 2 · 开发 Sprint 计划（2026-05-27 起）

> **真源**：[`docs/19` §六](../19-产品开发迭代计划-当前队列.md#六全量未闭环开发计划合并清单) · MVP 一期已 **v1.2.13 收口**  
> **刚上线**：M9 装备 / M11 学习路径 / M12 球手库 / M13 约球**后端** + Phase2 flags

---

## Sprint 排期（默认 2 周一迭代）

| Sprint | 主题 | PLAN-ID / 模块 | 交付物 | 状态 |
|--------|------|----------------|--------|------|
| **W1** | **约球客户端** | P2-M13-05 UI | `meetupService` + 列表 / 详情 / 发起页；「我的」入口可点 | **✅ Done**（`0968422`） |
| **W2** | **画像 2.0** | P2-M9-03 UI | onboarding 2.0 + 画像编辑页（对接已有 `profile-v2` API） | **✅ Done**（`5f0e9df`） |
| **W3** | **常去球馆 + 考核** | P2-M9-05 · P2-M11-04 | 球馆选择 UI；阶段考核 mock → 真实现 | **✅ Done**（`2f69ff0`） |
| **W4** | **引擎续做** | P2-M7-10 · M7-14 · M7-N1 | YAML 规则 starter + V2 路由打通 + drill 文案 D-6 | **✅ Done**（`e618a77`） |
| **W5** | **引擎深耕** | P2-M7-10 · M7-14 | V1→V2 全量 14 规则迁 YAML；features dict 外提让 V2 真正重诊 | **✅ Done**（`6afffda` · backend hotfix `a37499a`） |
| **W6** | **V2 灌溉** | ENG-A1 · ENG-A2 · ENG-A3 | metrics 观测 + redis 热改 pct + 离线 V1/V2 diff 脚本 | **✅ Done**（`816e320` · `915a6d2` uv.lock+test fix） |
| **W7** | **V2 引擎产品力 v0.1 落地** | P2-M7-02 · P2-M7-06 | engine_warnings + 三层 confidence 接入 V2；V1 行为冻结 | **✅ Done**（`a36eb88` 主体 · 待 hotfix `swing_start/swing_end` 注入） |
| **W8** | **V2 元数据探测灌入 engine_warnings** | P2-M7-02 · P2-W8 ENG-C | V2 入口 ffprobe 原始 URL → codec / hdr / slowmo / fps / audio 落入 `engine_warnings`；pipeline 主体仍走 V1，fps/timing 不变；探测失败静默兜底 | **✅ Done**（`4723bb0`） |
| **W9** | **V2 enrichment 精算** | P2-M7-06 · P2-W9 ENG-D | feature_confidence 按 landmark 子矩阵 × phase 窗口实算（不再一锅 mean_vis）；issue_confidence 按 feature value vs threshold 归一化距离实算（不再固定 td=0.5）；多 AND 条件取 min td；handedness 动态选 lead 手腕/肘 | **✅ Done**（`efa5f86` · review hotfix `69047a1`） |
| **W10** | **客户端 V2 兑现 · 服务端管道补全** | P2-M7-06 · P2-W10 | 修复 backend `_mark_completed` 完全丢弃 W7+W8+W9 字段的管道断点（`analysis_confidence` / `feature_confidences` / `engine_warnings` / `issue.confidence` / `confidence_tier`）；client `report.tsx` 接 TrustBadge（低 tier 弹重拍 CTA）+ hidden issues 折叠到「AI 不太确定」区 + V2 engine_warnings 调试浮层；alembic 0025 加 `swing_analyses.engine_warnings` 列 | **✅ Done**（`f7aa790` · 测试 fix `68f01ba` · CVM 4/4 backend + 18/18 client + alembic 0025 已生效） |
| **W11** | **V2 入口与分享面** | P2-M7-06 · P2-W11 | `GET /v1/analyses` 列表 schema 加 `engine_version` + `analysis_confidence`（V1 老报告兜底）；客户端历史卡片对 V2 报告贴「AI 高/中/低可信」mini 标签（V1 不渲染避免噪声）；`useShareAppMessage` / `useShareTimeline` 对 V2 **高可信**报告在 title 尾加「· AI 高可信」后缀；海报 `drawScoreCard` 在 V2 报告右上角画 trust compact 标签 | **✅ Done**（`5239943` + 测试 fix · CVM 8/8（W11 4 + W10 4）+ client 548/548 全过 + prod build 成功） |
| **W12-1** | **成长曲线 V2 tier 着色** | P2-M7-06 · P2-W12-1 | `AnalysisProgressPoint` schema 加 `engine_version` + `analysis_confidence`；service `get_user_analysis_progress` 透传两字段；client `ProgressLineChart` 圆点按 trust tier 着色（高=mint / 中=gold / 低=warning），折线保持 accent 色保证视觉连续；V1 老报告不上 tier 走原色 | **✅ Done**（`8578cf6` · CVM backend 11/11 + client 550/550） |
| **W12-2** | **V2 引擎产品力 v0.2 · 机位标尺接入** | P2-M7-04 · P2-M7-06 · P2-W12-2 | `_enrich_v2` / `_enrich_v2_fallback` 调 `_summarize_pose_for_angle` + `detect_camera_angle` 把 `offset_deg` 真喂给 `compute_analysis_confidence`（之前写死 None）；偏角 >15° 触发 `ANGLE_PENALTY_BAD=0.6` 真惩罚 confidence；`angle_engine_warnings` 追加进 `result.engine_warnings`；`run_real_analysis_v2` 末尾改成"合并"而非"覆盖"避免 angle warning 被 probe / fallback 吞掉 | **✅ Done**（`8578cf6` · CVM ai_engine 93/93 全过 含 W7+W8+W9+W12-2/3 回归） |
| **W12-3** | **MinIO ffprobe 5XX 治理** | P2-M7-02 · P2-W12-3 | `_probe_with_retry` 5xx/timeout 指数退避 retry 2 次（共 3 attempts，4xx/binary_missing 不 retry）；`_classify_probe_error` 按 5xx/4xx/timeout/binary_missing/unknown 分桶；`_sanitize_probe_url` 去 query string 防 X-Amz-Signature 泄漏；失败时不再静默返回 [] 而是返回 `probe_failed` engine_warning 让客户端调试浮层能看到原因；新增 6 个分桶 metrics（`v2_probe_retries` + `v2_probe_errors_{reason}`） | **✅ Done**（`8578cf6` + 测试 fix · CVM ai_engine 93/93） |
| **W13-A** | **进步曲线 trust tier 图例** | P2-M7-06 · P2-W13-A | 新建 `TrustTierLegend` 组件（mint/gold/warning 三色 + 一句话说明），插到 training/index `ProgressLineChart` 下方；仅当当前 chartSeries 含 V2 tier 时显示（全 V1 报告不渲染避免噪声）；色块 className 与 ProgressLineChart Canvas tier key 严格对齐防止改色失同步 | **✅ Done**（`a0250de` · client 554/554） |
| **W13-B** | **V2 引擎产品力 v0.3 · mismatch 兜全** | P2-M7-04 · P2-M7-06 · P2-W13-B | `PipelineCtx` 加 `declared_camera_angle` 字段（向后兼容默认 None）；`run_real_analysis` 从 `req.camera_angle` 透传；`_enrich_v2` / `_enrich_v2_fallback` 调 `attach_declared` 让 mismatch warning 真生成；未知 declared alias 不阻塞主流程，吞 ValueError + log info | **✅ Done**（`a0250de` · CVM ai_engine 14/14 camera_angle） |
| **W13-C** | **MinIO ffprobe 5XX 根治** | P2-M7-02 · P2-W13-C | RCA 出根因：ai_engine 收到的 `video_url` 是公网 URL，ffprobe 绕 4 跳走"容器→公网 DNS→CVM nginx 443→/minio/→minio:9000"；新增 `_rewrite_to_internal_url` 在 `_probe_video_warnings` 入口把 `MINIO_PUBLIC_ENDPOINT` 前缀替换为 `MINIO_ENDPOINT`，让 ffprobe 走单跳 docker 内网，彻底绕开 nginx /minio/ 反代这一 5xx 风险源；不命中前缀（COS/第三方）/endpoint 缺失/两者相等（dev）均原样返回，仍走 W12-3 retry 兜底；docs/release-notes/minio-ffprobe-5xx-rca.md 写完整根因链路 + 修复 + 验证 | **✅ Done**（`a0250de` + 测试 fix `c0c1d17` · CVM ai_engine 35/35 probe；线上观察期 7d） |
| **W13-D** | **ai_engine Prometheus alerting** | P2-W13-D | ai_engine `/metrics/prom` 端点输出 Prometheus exposition v0.0.4 文本格式（不引 `prometheus_client` 依赖，手写 5 行渲染）；自动区分 counter/gauge（`_rate` / `_ratio` / `_pct` / `_avg_latency` / `mock_mode` / `uptime_s` → gauge）；W12-3 新增 6 个 metric 全部 export；新建 `infra/monitoring/prometheus-alerts.yml` 7 条告警分 P0/P1/P2 三级（V2 错误率 / V2 fallback burst / probe 失败率 / MinIO 5xx 回潮 / 流量比偏离 / V2 平均耗时 / enrichment 兜底趋势） | **✅ Done**（`a0250de` · CVM admin 13/13 + `/metrics/prom` 实际返回标准 HELP/TYPE/value 三段） |
| **W14-A** | **Prometheus + Alertmanager 容器化** | P2-W14-A | docker-compose 加 `prometheus`/`alertmanager`/`webhook-echo` 3 个 service 走 `profile: ["monitoring"]`（默认不启不影响主链路）；`infra/monitoring/prometheus.yml` scrape ai_engine `/metrics/prom` + 加载 W13-D rule_files；`infra/monitoring/alertmanager.yml` 按 severity 路由 page/warn/info 三档 + 抑制规则；webhook 默认指向 echo 占位（接企业微信/钉钉等生产渠道留 W18+）；监控端口全部 bind `127.0.0.1:` 不暴露公网（走 SSH 端口转发）；`infra/monitoring/README.md` 写起动/转发/故障排查 | **✅ Done**（`9ca9b2f` · `docker compose --profile monitoring config` 校验通过；CVM 待手动开 `--profile monitoring up`） |
| **W14-B** | **客户端 camera_angle_mismatch 友好 banner** | P2-W14-B · M7-04 | 新建 `CameraAngleAlert` 组件把 W13-B `camera_angle_mismatch` + W12-2 `camera_angle_large_offset` 翻译成"你选的是正面，AI 看到的更像侧面"中文文案；插到 report.tsx `TrustBadge` 下方、`qualityWarningLines` 上方；两个 code 同时存在合并到同一 banner 不堆两块；detail 解析失败走兜底文案不崩；amber 边色不上 error 红不吓人；与 W10 debug 浮层共存（这里给 C 端，那里给 PM/教研） | **✅ Done**（`9ca9b2f` · client 563/563 + W14-B 9 例） |
| **W14-C** | **真实流量 V1/V2 diff 校准 runbook** | P2-W14-C · 接 W6 ENG-A3 + W13-D | CVM 现场体检发现 0 真实流量（89 条 completed 报告 `video_url` 全是 dummy `https://x/v.mp4`，sample fixture OSS URL 已 404）；W14-C 不强行跑 fake baseline（噪声会污染后续阈值校准），而是写 `docs/release-notes/v1-v2-diff-real-traffic.md` 完整 runbook：4 个触发条件（≥20 真实样本 / fallback 告警 fire / 回滚证据 / 月度趋势）+ 5 步操作（拉 CSV → 容器跑脚本 → 拉报告 → 看 4 个指标 → 归档）+ W13-D 两条 alerting 阈值的校准入口；现场验证 `v1_v2_diff.py` 脚本本身在 CVM 容器内可执行（client_error 也不崩） | **✅ Done**（`9ca9b2f` · CVM 体检表 + 4 触发条件 + 5 步操作 + 阈值校准入口完整 runbook） |
| **W14-D** | **抽 app/integrations/probe.py 模块** | P2-W14-D · 接 W12-3 + W13-C | 新建 `ai_engine/app/integrations/probe.py`，把 `_sanitize_probe_url` / `_rewrite_to_internal_url` / `_classify_probe_error` / `_ProbeRetryOutcome` / `_probe_with_retry` / `_probe_video_warnings` 从 `real_pipeline_v2.py` 整体迁出（公开名去掉下划线）；`real_pipeline_v2.py` 保留下划线 thin re-export 维持 W12-3/W13-C 现有 30+ 测试 import 路径；测试 monkeypatch 路径从 `rp2_mod` 改到 `probe_mod`（21+3+4+2=30 处分两轮 hotfix）；为 W16+ backend probe 集成 / W18+ 切 COS 时复用铺路 | **✅ Done**（`9ca9b2f` + 测试 hotfix `af93586` `becb2ba` · CVM ai_engine 62/62 全过；CVM `/metrics/prom` v2_probe_* 仍正常 export） |
| **W15-A** | **CVM 真启动 W14-A 监控栈** | P2-W15-A · 接 W14-A | CVM 上 `docker compose --profile monitoring up -d prometheus alertmanager webhook-echo`；解决初次启动 `error from registry: unknown error`（compose 拉 ealen/echo-server 国内不可达），换 `mendhak/http-https-echo:31` HTTP_PORT=9094；验收 Prometheus targets `ai_engine/prometheus` 双 UP + 7 条 W13-D 告警规则全加载；Alertmanager 0.27.0 ready；webhook-echo HTTP 200；端口全部 `127.0.0.1` 绑定走 SSH 转发 | **✅ Done**（`docker-compose.yml` webhook-echo 镜像替换 · CVM 三容器 Up） |
| **W15-B** | **sample fixture URL 修复** | P2-W15-B | CVM `MINIO_BUCKET=xiaoniao-videos-test` 下 `samples/` 是空的导致 `/v1/analyses/sample` 视频 404；用 ai_engine 容器自带 ffmpeg 合成 5s 720×1280 靛蓝底+金字水印占位 mp4 + 抽帧 jpg → MinIO `samples/swing_demo.mp4` + `samples/swing_demo_thumb.jpg`；`/v1/assets/image/{key}` 加 HEAD 支持避免 cache 健康检查 405；写 `infra/deploy/seed-sample-fixture-to-minio.sh` 幂等脚本（FORCE=1 强制覆盖）让下次重置环境一行复原；公网 HEAD video 200 + GET image 200 + `/v1/analyses/sample` 返回的 URL 实际可访问 | **✅ Done** |
| **W15-C** | **monitoring runbook + 7 告警响应表 + 7d 检查项** | P2-W15-C | `docs/release-notes/monitoring-runbook.md`：监控栈拓扑 + 7 条告警逐条 Trigger/Verify/Mitigate/RootCause/Document 五段式响应表 + W13-C 落地后 7 天观察检查项（D0/D1/D3/D7 关键指标基线）+ 周报模板 + W18+ 接生产渠道 backlog + 每月演练流程；同步 D0 基线值（v2_count=0/v2_probe_*=0，rollout=100% / mock_mode=false） | **✅ Done** |
| **W15-D** | **probe._rewrite_to_internal_url 泛化** | P2-W15-D · 接 W13-C | 新增 `EXTRA_INTERNAL_URL_REWRITES` 设置（分号分隔 `<public>=<internal>` 对）；`_iter_rewrite_pairs` 收集 MinIO + extra 对（MinIO 始终优先以保 W13-C 向后兼容）；`rewrite_to_internal_url` 多 pair 顺序 startswith 命中即返回；W18+ 切 COS / OSS / 七牛时只改 env 不改代码；新加 5 单测覆盖单 pair / 多 pair 优先级 / MinIO 优先 / 非法格式跳过 / 空字符串等价于 MinIO 单对 | **✅ Done**（CVM ai_engine 9/9 rewrite + extra_rewrite 全过） |
| **W16-A** | **score-percentile API + service** | P2-W16-A · ENG-05 | 新增 `GET /v1/users/me/score-percentile?club_type=` API：cohort 同 `User.golf_level` + 同 `club_type` 其他用户最近一次完成态分析综合分；`_calc_percentile`/`_calc_median`/`_format_percentile_cohort_label` 三个纯函数；样本量 < 5 → percentile/median = null（UI 隐藏）；用户没填 golf_level 时 cohort 不限定 level（"全部水平"）；服务端只返聚合（cohort_size/median/percentile）不暴露他人 user_id；DB 用窗口函数 ROW_NUMBER 取每用户最新 club_type 完成态分析 | **✅ Done**（CVM backend 21/21 含 11 纯函数 + 10 端到端 DB） |
| **W16-B** | **client 训练页分位 UI** | P2-W16-B · ENG-05 | `userService.getScorePercentile`；新建 `ScorePercentileCard` 组件（百分位大数字 + cohort_label + 你/群体中位/样本三列 meta + 颜色梯度 ≥75 金 / ≥50 主色 / <50 灰，避免"刚击败 5%"的视觉鼓励误读）；插到训练页 `TrustTierLegend` 之后、进步曲线 narrative 之前；data=null / percentile=null / user_score=null 整卡不渲染（cohort_size<5 服务端约定的 UI 隐藏路径）；MVP 期固定查 `iron_7`（W17+ 加切换器）| **✅ Done** |
| **W16-C** | **朋友圈封面海报 layout 工具** | P2-W16-C · Q-B2 余量 | 新建 `client/src/utils/posterTimelineLayout.ts`：1080×1920（朋友圈封面 9:16）三段式 Y 区版式（hero 0-640 信息流首屏 / detail 640-1440 雷达+issues / cta 1440-1920 扫码+水印）+ 各区元素锚点 + `verifyTimelineLayout` 健康检查 + 22 jest 测试；UI 接入留 W19+（产品策划未拍板时不强推半成品；layout 工具就位等触发） | **✅ Done**（22/22 单测 · 进 W19+ 触发清单） |
| **W16-D** | **W16 单测收口 · client 598/598 全绿** | P2-W16-D | ScorePercentileCard 14 jest（不渲染分支 / 正常态 / 颜色梯度 / rightSlot）+ posterTimelineLayout 22 jest + W16-A 21 backend pytest；client 全量 jest 60 suites / 598 tests 全过；backend 全量回归不污染（W16-A 测试用 unique club_type 隔离 prod 数据）| **✅ Done** |
| **W17-A** | **par-E3 网络 Toast 映射余量** | P2-W17-A · par-E3 | `friendlyNetworkMessage` 加 errcode 模式扩展（必须在 fail+connect 通配前）：微信真机 -100/-99 代理拒绝 → "关闭抓包/VPN" / -2 协议错误 → "响应不规范" / iOS CFNetwork errno=-1003 cannot find host → "找不到服务器地址" / errno=-1009 not connected → "当前没有网络连接"；HTTP 429 单独识别（status=429 + 空 body 不再落 'bad_response' 模糊文案，toast "请求过于频繁" + 保留 RequestError 让 hook retry 退避）；新增 7 条单测（5 errcode 扩展 + 2 HTTP 429 silent/normal）32/32 全过 | **✅ Done** |
| **W17-B** | **par-T1 pytest 关键路径覆盖确认** | P2-W17-B · par-T1 | 实际盘点：chat 36 测试（lifecycle/streaming/attachments/topic boundary/content security 5 文件）+ feedback 5 测试（ok/blank/too_long/auth/rate_limited 全覆盖 service raise 路径）+ meetup 38 测试（service/responses/meetups api 3 文件）；关键边界已经满覆盖，无新增需求；继续保持 chat / feedback / meetup 任何 service 改动同步加 pytest 的 W4 起约定 | **✅ Done**（盘点确认） |
| **W17-C** | **DOC-05 全文档巡检 + 回填** | P2-W17-C · DOC-05 | sprint plan W15-W17 全条目回填 + 真实状态；`wait-for-triggers-checklist.md` 单文件汇总 11 条等触发项（O-01/O-04/P-02/W14-C/Q-B5/Q-D1/ENG-04/ENG-06/W18+ webhook/W18+ COS/W19+ timeline poster）每条触发条件可观测、动作落 owner、证据进 doc | **✅ Done** |
| **W17-D** | **ENG-06 争议样本周更模板** | P2-W17-D · ENG-06 | `docs/release-notes/eng-06-disputed-sample-weekly-template.md`：数据源 P0-P3（in-app/教练/客服/标定）+ 周报 markdown 模板（数据 + 样本明细表 + 行动项 + 不入档说明 + 下周关注）+ 工程化 4 项最低要求（analysis_id/标注/AI 输出/PLAN-ID）+ 反例 + 落地清单（cp 模板 → 填表 → PR）；首版样例 W17 空跑（v2_count=0 真流量未起，等触发） | **✅ Done** |
| **W17-E** | **等触发清单收口** | P2-W17-E | 见 W17-C；11 条等触发项集中到 wait-for-triggers-checklist.md 一份；维护契约：每月 1 次扫表 / 触发即更新 / 不要扩散；反模式排雷（不可观测条件 / 没 owner / 工程未就位） | **✅ Done** |

**并行泳道（不占 Sprint 主表）**：U-2 COS · Q-B5 papay · O-01/O-04 性能抽测 · par-E3/par-T1

**线上灰度状态**：W5 部署后 V2 pct=5（`.env.local`，CVM 容器内验证 1000 user_id → 49 命中 V2 ≈ 4.9%）。

---

## W1 · 约球客户端验收

| # | 验收项 |
|---|--------|
| 1 | `PHASE2_MEETUP_ENABLED=true` 时「我的 → 约球邀请」进入列表页，不再 toast |
| 2 | 列表分「全部 / 收到的 / 发出的」，展示状态与时间 |
| 3 | 详情页：被邀请人 pending 可接受/拒绝；邀请人 pending 可撤回 |
| 4 | 接受时可填会面备注（`note` / `meet_at`，不含手机号等） |
| 5 | 发起页：`?invitee=` 传入被邀请人 id；可选留言与时间 |
| 6 | `meetupService` Jest 单测覆盖 URL / method |

---

## W2 · 画像 2.0 验收

| # | 验收项 |
|---|--------|
| 1 | `PHASE2_PROFILE_V2_ENABLED=true` 时新用户走 **6 步** onboarding |
| 2 | 完成引导写入 `profile-v2` + v1 `onboarding_completed` |
| 3 | 「我的 → 我的画像」可查看/编辑并保存 |
| 4 | 伤病勾选有二次确认；`profileV2Mapping` 单测通过 |

---

## W4 · 引擎续做验收（本批为「起跑前置」交付）

| # | 验收项 |
|---|--------|
| 1 | `ai_engine/app/pipeline/rules/v2_starter.yaml` 含 5 条 V1→V2 入门规则；互斥矩阵双向声明 |
| 2 | `ai_engine/app/pipeline/locales/zh_CN.json` 每条规则都有 `.title` + `.summary` 模板 |
| 3 | `load_rules_from_yaml()` schema 校验 + `RuleEngine` 端到端 trigger / locale 渲染单测覆盖 |
| 4 | `ai_engine/app/pipeline/real_pipeline_v2.py` 暴露 `run_real_analysis_v2`/`diagnose_v2`；main.py 按灰度桶分流 |
| 5 | V2 资源加载失败 → fallback 到 V1，不影响线上 |
| 6 | `backend/app/services/chat_service.py` video_card title 后缀对齐前端 `· 教练示范`（D-6） |

> **本批不含**：13 V1 规则全量迁移、ECS 触发率验证（M7-10 W29-W33）；features dict 外提到 `diagnose_v2` 重诊（M7-14 W34）；drill 视频拍摄（M7-N1 Phase 2.1 W14-W17）。

---

## W5 · 引擎深耕验收

| # | 验收项 |
|---|--------|
| 1 | `v2_starter.yaml` 扩到 14 条规则，覆盖 V1 `_RULES` 全部 issue（`grip_weak` 占位除外） |
| 2 | 每条规则带 `phase_anchor`（setup/backswing/top/downswing/impact/follow_through），schema 校验非法值 |
| 3 | `locales/zh_CN.json` 14 条 `.title` + `.summary` 模板齐全 |
| 4 | 互斥矩阵：`early_extension`↔`loss_of_posture`、`over_rotation`↔`under_rotation`、`flat_shoulder`↔`steep_shoulder`、`loss_of_posture`↔`sway_slide` 全部双向 |
| 5 | `real_pipeline.run_real_analysis(diagnose_fn=...)` 可注入诊断实现；`run_real_analysis_v2` 注入 `diagnose_v2` 真正用 YAML 重诊 |
| 6 | `diagnose_v2` 接受 `PhaseSegmentResult` 并按 `phase_anchor` 填 `key_frame_timestamp` |
| 7 | V2 资源加载失败 → `diagnose_fn=None` → 回落 V1 `diagnose` |
| 8 | 新增单测：YAML 全集与 V1 `_RULES` 类型集合对齐、phase_anchor / locale summary 全覆盖、key_frame_timestamp 端到端 |

> **仍留 backlog**：ECS 影子流量比对（M7-10 W34 AC-1）；P2-M7-02 engine_warnings + P2-M7-06 issue_confidence 三层模型（W34）。

---

## W6 · V2 灌溉验收

> **目标**：让 V2 灰度可观测、可热改、可定量对比，**为推 50% → 100% 铺路**。

| # | 验收项 |
|---|--------|
| 1 | `ai_engine` 内进程级计数器：`v1_count` / `v2_count` / `v2_errors` / `v1_errors`；新增 `GET /metrics` 返回 JSON（含 pct + 各计数 + uptime_s） |
| 2 | `analyze_done` structlog 字段含 `engine_version`（已在 W4 落地）；本批补 `engine_v2_fallback` warning（V2 资源加载失败回落 V1 时） |
| 3 | `ai_engine/pyproject.toml` 新增 `redis>=5,<6`；`set_rollout_pct` 写 Redis 成功（不再 `ModuleNotFoundError`），多容器场景下 60s TTL 内全 ai_engine 实例对齐 |
| 4 | `/admin/engine-rollout` 端点支持可选 `X-Admin-Token` 鉴权（环境变量 `AI_ENGINE_ADMIN_TOKEN` 配置；未配则保持向后兼容允许内网调用） |
| 5 | `scripts/v1_v2_diff.py`：输入 N 个 swing_analysis_id → 各以 `force_engine_version` 强制跑 V1 / V2 → 输出 diff CSV（issues 类型集合 / 各 issue severity / overall_score）+ 一致率汇总 |
| 6 | 单测：metrics 计数器 race-safe、Redis 路径 mock 注入、`/admin/engine-rollout` 鉴权 401/200 路径 |
| 7 | 生产 smoke：`curl http://ai_engine:9100/metrics` 看到 v1/v2 计数随真实流量增长；CVM 内 `python -c "set_rollout_pct(5)"` 写入 Redis 成功 |

---

## W7 · V2 引擎产品力 v0.1 验收

> **目标**：把 `engine_warnings.py` + `confidence.py` 这两个早就建好但没接入生产
> 的 v0.1 模块，**真正落进 V2 pipeline**——让灰度用户的报告带上三层可信度，
> 客户端能据此折叠 `hidden` 诊断、低 `analysis_tier` 时弹「建议重拍」CTA。

> **不做项（留 W8+）**：V2 切到 `phases_v2 / preprocess_v2`（让 engine_warnings 真有
> codec / fps / 机位等内容）；逐特征精算 `feature_confidence`（按 FEATURE_LANDMARKS_MAP
> 取 visibility 子矩阵而非全局 mean）；`issue_confidence` 按 feature value 与 condition
> threshold 实算 `threshold_distance`。

| # | 验收项 |
|---|--------|
| 1 | `real_pipeline.run_real_analysis` 新增 `enrichment_fn: Callable[[AnalyzeResult, PipelineCtx], None] \| None = None`；V1 默认 None → 行为冻结（IssueItem.confidence=None / analysis_confidence=1.0 / engine_warnings=[]） |
| 2 | `PipelineCtx` frozen dataclass 暴露 pose_result / phases / features / quality_warnings / fps；hook 内仅读不改 ctx |
| 3 | `real_pipeline_v2._enrich_v2` 实现三层：Layer 1 feature_confidences 用 `pose.mean_confidence` 全填（MVP）；Layer 2 按 rule.conditions 找 feature 求平均喂 `issue_confidence`；Layer 3 `compute_analysis_confidence`，camera_angle_offset_deg 暂 None |
| 4 | IssueItem.confidence_tier ∈ {confirmed / leaning / hidden}（confidence.py 已有 `issue_tier`） |
| 5 | `run_real_analysis_v2` 注入 `enrichment_fn=_enrich_v2`；V2 fallback 时（YAML 加载失败）engine_warnings 多塞一条 `fallback_to_v1`，让客户端可见 |
| 6 | `enrichment_fn` 抛错被 `run_real_analysis` try/except 吞掉 + log `enrichment_fn_failed` warning；主报告不受影响 |
| 7 | 单测：三层端到端 / hidden 过滤 / low tier retake / V1 默认值兼容 / 零帧 pose 不挂 |
| 8 | 生产 smoke：CVM 容器内 pytest 通过；线上 V2 路径返回 result 含 `analysis_confidence > 0`、`feature_confidences != {}`、issues.confidence ≠ null |

---

## W8 · V2 元数据探测灌入 engine_warnings 验收

> **目标**：让灰度用户的 V2 报告 `engine_warnings[]` 从 W7 的「只在 fallback 时
> 写一条 `fallback_to_v1`」升级为「正常路径就反映原始视频 codec / hdr / 慢动作
> / 帧率 / 音频」实情。**pipeline 主体仍走 V1，不动 fps / phases timing**。

> **不做项（留 W9+）**：真正把 V2 切到 `preprocess_video_v2`（fps 改 60 → 下游
> timing 全部要重校）；切到 `phases_v2`（NN 模型 W23-W26 才能就绪，当前 fallback
> 只多写 `phase_seg_nn_not_ready` 一条 info）；机位类码 `camera_angle_*`（要先
> 接 P2-M7-04 camera_angle 模块）。

| # | 验收项 |
|---|--------|
| 1 | `preprocess_v2._ffprobe_extended` 签名扩成 `video_path: Path \| str`；ffprobe 自身直接接 HTTP(S) URL，无需先下载视频 |
| 2 | `real_pipeline_v2._probe_video_warnings(video_url) -> list[EngineWarning]` 新增；按 probe 结果生成 `decoded_h264 / decoded_hevc / decoded_vp9 / hdr_tonemapped / slowmo_detected / nominal_fps_used / fps_upsampled / fps_downsampled / audio_kept / audio_dropped` 中的若干条 |
| 3 | 所有产出 code 都在 `engine_warnings.KNOWN_CODES` 白名单内（含 `decoded_h264`，已在 M7-02 注册） |
| 4 | `run_real_analysis_v2` 在 V1 pipeline 调用前先跑 probe；成功后把 probe warnings + fallback warning（若有）合并 `serialize_engine_warnings` 写到 `result.engine_warnings` |
| 5 | probe 失败（network / 私有 URL / 二进制缺失）静默 `return []` + log `v2_probe_failed_silently`；**绝不**抛异常打断主分析；客户端能看到一份没有 codec warning 的正常 V2 报告 |
| 6 | 单测覆盖：h264 / hevc / h265 alias / vp9 / 未知 codec；HDR vs SDR；慢动作（fps_raw=240, nominal_fps=30）；fps 30/60/120/0；音频有无；多类组合（iPhone HEVC HDR 慢动作）；ffprobe 抛错静默；空 URL；KNOWN_CODES 白名单；集成 `run_real_analysis_v2` 合并 probe + fallback |
| 7 | 生产 smoke：CVM 内 pytest `tests/test_real_pipeline_v2_probe.py` 全过；线上 force `engine_version=v2` 真视频 `result.engine_warnings` 出现 `decoded_*` + `audio_*` 等元数据条目 |

---

## W9 · V2 enrichment 精算验收

> **目标**：把 W7 的 confidence MVP 从「全部用 mean_visibility + 固定 td=0.5」升级到
> **逐特征看 landmark 子矩阵 + 逐 issue 按阈值距离实算**。同一段视频里不同特征
> 的 confidence 会真有差异（脚踝可见但肩腕被遮 → finish_balance 高、spine 低）；
> issue 触发值越远离阈值 → confidence 越接近 confirmed。

> **不做项（留 W10+）**：
> - `compute_analysis_confidence` 接 `camera_angle_offset_deg`（等 P2-M7-04 落地）
> - 把 W9 的 `_STATIC_FEATURE_LANDMARKS` 表回填到 `confidence.py` 通用层
>   （当前因为有 lead/trail 动态分支，保留在 `real_pipeline_v2.py` 私有）
> - features.py 提取过程内部直接用 landmark visibility 加权（仍依赖 features dict 外提）

| # | 验收项 |
|---|--------|
| 1 | `real_pipeline_v2._STATIC_FEATURE_LANDMARKS` 覆盖 `constants.FEATURES` 全部 15 项中 10 项静态特征；`_lead_landmark_indices` 覆盖余下 5 项手别相关特征（`top_wrist_position / wrist_release_angle / wrist_release_timing / tempo_ratio / finish_height`） |
| 2 | `_feature_phase_frames(feature, phases, num_frames)` 按 phase 取窗口：setup 类用 `setup.key_frame ± 2`；top 类用 `top_frame ± 2`；rotation 类拼 setup + top window；downswing 用区间；wrist_release 用 [top..impact]；全程类用 [swing_start..swing_end]；finish_balance 用尾 10 帧 |
| 3 | `_visibility_sub_for_feature(pose, phases, name)` 返回 `(F_window, K_landmarks)` list[list[float]]；num_frames=0 / phases=None / 未知特征 → `[]`；下游 `feature_confidence([])` 返回 0.0 不浮报 |
| 4 | `_compute_threshold_distance(value, condition)` 按 ideal_max-ideal_min 归一化 scale；`>` / `>=` 在 value>threshold 命中方向才有正 td，反方向 td=0；`<` / `<=` 对称；clamp 上限 5.0；未知特征 scale=1.0 兜底 |
| 5 | `_issue_threshold_distance(rule, features)` 多 AND 条件取 **min td**（短板原则）；缺失特征当 td=0；空 rule 返回 0 |
| 6 | `_enrich_v2` 重写：Layer 1 调 `_visibility_sub_for_feature` + `feature_confidence` 实算 → 写 `result.feature_confidences`；Layer 2 调 `_issue_threshold_distance` 算 td → 喂 `issue_confidence(..., threshold_distance=td)`；Layer 3 用精算后的 dict 喂 `compute_analysis_confidence`；V1-only issue 类型仍兜底 mean_vis |
| 7 | 单测覆盖：lead/trail 手别判定；phase frame 窗口（含 num_frames=0 边界）；visibility 子矩阵抠取；td 各 operator + scale 归一化 + clamp；issue td 短板；端到端 enrich——脚踝可见但肩腕遮挡时 finish_balance 高 / spine 低、issue 远离阈值 conf 高 / 临界值 conf 低、左右撇子 lead 手别正确切换 |
| 8 | W7 老测例 `test_real_pipeline_v2_enrich.py` 在 visibility 一致场景下仍 pass（公式向下兼容） |
| 9 | 生产 smoke：CVM 容器内 W9 新单测全过；V2 路径 `analyze_done` log 输出 `feature_conf_min/max` 区分度（非全部相等） |

---

## W11 · V2 入口与分享面验收

> **目标**：把 W7+W8+W9+W10 的服务端 V2 能力**沿用户路径再往前推一步**：
> 历史列表 → 报告详情 → 海报 → 分享 title，让 V2 报告在每个入口都有一致的
> 「AI 高/中/低可信」信号面，**不只是点开报告才看得见**。

> **不做项（留 W12+）**：
> - 「我的-成长曲线」上把 trust tier 拉成时间序列（依赖 progress API 新字段）
> - 反向：从历史卡片直接长按调出"建议重拍"（侵入性高，需产品先决策）
> - 列表筛选「只看 V2 报告」入口（V2 100% 后预期一段时间内 V1/V2 并存窗口很短）

| # | 验收项 |
|---|--------|
| 1 | `AnalysisListItem` schema 加 `engine_version: Literal["v1","v2"]="v1"` + `analysis_confidence: float \| None = None`；老 V1 报告兜底 `engine_version="v1"` / `analysis_confidence=None` 不抛 ValidationError |
| 2 | `services/analysis_service.list_analyses` 透传两字段；`_coerce_list_confidence` 处理 NaN/Inf/越界 → None / clamp，不让边界值抛 500 |
| 3 | 客户端 `types/analysis.AnalysisListItem` 加可选字段；`history.tsx` 在 V2 报告卡片 `info-head` 右侧贴 `formatTrustMiniLabel` 小标签；V1 / 未完成 / analysis_confidence=null 时不渲染 |
| 4 | `history.scss` `__trust--high/medium/low` 三档配色严格走 CSS 变量（mint-soft / gold-soft / warning-soft），不硬编码 HEX |
| 5 | `report.tsx` `useShareAppMessage` / `useShareTimeline` 调 `buildShareTrustSuffix`：V2 + 高可信 → title 加「· AI 高可信」后缀；其它情况 / V1 / publicReport 不动 |
| 6 | `trustLabel.formatTrustMiniLabel` 新增；单测覆盖 high/medium/low 三档 + null 兜底 |
| 7 | backend 单测 `test_w11_list_v2_fields.py` 4 例全过：V2 透传、V1 兜底、clamp 越界、`_coerce_list_confidence` NaN/Inf/字符串 |
| 8 | CVM 部署：backend pytest W11 4/4 + W10 4/4 + client `client-test` 537+ 回归全过；客户端 `client-build-weapp-prod` 出包供体验版上传 |

---

## 文档债（W1 后补）

- [`docs/02`](../02-API接口设计文档.md) 增补 M13 约球 / venues 端点（后端已落地，文档未同步）

---

## 文档变更记录

| 日期 | 说明 |
|------|------|
| 2026-05-27 | 初始化 W1–W4 Sprint；W1 约球 UI 开工 |
| 2026-05-28 | W1 ✅（`0968422`）；W2 画像 2.0 UI 开工 |
| 2026-05-28 | W2 ✅（`5f0e9df`）：6 步 onboarding + 我的画像编辑页 |
| 2026-05-28 | W3 ✅（`2f69ff0`）：常去球馆页 + 课程详情阶段考核 UI |
| 2026-05-28 | W4 ✅（`e618a77`）：M7-10 YAML loader + starter 5 规则 + locale；M7-14 `real_pipeline_v2` + main.py 灰度路由；M7-N1 D-6 修复 |
| 2026-05-28 | W5 ✅（`6afffda`）：YAML 全量 14 规则 + `phase_anchor` + `diagnose_fn` 注入；V2 通过 features 真正重诊。backend hotfix `a37499a` 修 W3 `lessons.py` import 错路径 |
| 2026-05-28 | W5 部署：`make publish-backend-cvm`；`.env.local` 加 `M7_V2_ROLLOUT_PCT=5`，V2 灰度 5% 生效；W6 V2 灌溉开工 |
| 2026-05-28 | W6 ✅（`816e320` 主体 + `915a6d2` uv.lock 补 redis & test 隔离）：CVM 容器内 18/18 单测过；`/metrics` 端点返回完整 JSON；Redis 持久化验证通过（set→另一进程 force_refresh 能读到）；线上 pct 由 Redis 接管，业务真值仍为 5 |
| 2026-05-28 | W7 ✅（`a36eb88` 主体）：`run_real_analysis` 加 `enrichment_fn` hook + `PipelineCtx`；`_enrich_v2` 接三层 confidence + tier 进 V2 报告；fallback 时 engine_warnings 塞 `fallback_to_v1`；CVM 12/12 enrich 单测过；待 hotfix 把 `swing_start/swing_end` test fixture 补全后随下次 publish 入 image |
| 2026-05-28 | W8 In Progress：`_ffprobe_extended` 接受 str URL；`real_pipeline_v2._probe_video_warnings` 落地 10 种 codec/hdr/slowmo/fps/audio engine_warnings；`run_real_analysis_v2` 在 V1 之前跑 probe 并合并到 result；`test_real_pipeline_v2_probe.py` 22 例覆盖正常/边界/失败/集成；pipeline 主体 fps 仍 30，下游 timing 不变 |
| 2026-05-28 | W8 ✅（`4723bb0`）：CVM 21/21 probe 单测过；真 fixture 视频探测端到端产 `decoded_h264 / fps_upsampled / audio_dropped` 三类 warnings；`/metrics` 端点正常、`rollout_pct=5` 灰度未受影响 |
| 2026-05-28 | W9 In Progress：`real_pipeline_v2` 加 15 项 feature→landmark 静态表 + 5 项手别动态表；`_feature_phase_frames` 覆盖 7 类 phase 选窗口；`_compute_threshold_distance` 按 ideal scale 归一化；`_enrich_v2` 重写精算 Layer 1/2；新增 `tests/test_real_pipeline_v2_enrich_precise.py` 38 例（lead/trail / phase frames / sub matrix / td / 端到端） |
| 2026-05-28 | W9 ✅（`efa5f86`）：CVM 73/73 V2 enrich 全单测过（W7 12 + W8 21 + W9 40）；`scripts/w9_smoke.py` 端到端验证脚踝单独可见时 `finish_balance=0.95`、`spine_*=0`、`head_lateral_shift=0`，`analysis_confidence=0.09` 触发"建议重拍"——W7 MVP 公式下会全部浮报到 mean_vis，W9 精算公式真实反映遮挡 |
| 2026-05-28 | W10 ✅（`f7aa790` + 测试 fix `68f01ba`）：backend `_mark_completed` 落 6 字段 + `get_report` 返出；client `report.tsx` 接 TrustBadge + hidden 折叠 + engine_warnings 调试浮层；alembic 0025 CVM 已生效；backend 4/4 + client 18/18 + 537/537 回归全过 |
| 2026-05-28 | V2 灰度 → 100% 切流：诊断发现 11 天历史 4 个真实用户 md5 hash 集中在 [81,91]，5%/10%/25%/50%/75% 灰度全部 0 命中（统计巧合 + sticky 分桶副作用）；事务清理 4 条 W10 测试污染（删 4 user + 4 analysis + 8 issues + 4 recos）；通过 admin endpoint 一键 `set_rollout_pct(100)`；主力 user 端到端冒烟 V2 真路径 ✅：`engine_version=v2 / analysis_confidence=0.806 / 15 个 feature_confidences / 5 个 issues 含 confirmed/leaning/hidden 三 tier`，落库等下次真用户上传自动生效 |
| 2026-05-29 | W11 ✅（`5239943` + 测试 fix）：backend `AnalysisListItem` schema 加 `engine_version` + `analysis_confidence`，`list_analyses` 透传，新增 `_coerce_list_confidence` sanitize NaN/Inf/越界；client `history.tsx` V2 卡片贴「AI 高/中/低可信」mini 标签，配色 mint/gold/warning soft；`useShareAppMessage`+`useShareTimeline` 在 V2 高可信报告 title 尾加「· AI 高可信」后缀；海报 `drawScoreCard` 在 V2 右上画 trust compact 标签；附带跨页 UI 适配（courses/pros/profile/index/meetup 共 11 页 SCSS：width/min-width/flex-shrink/word-break/safe-area-inset-bottom）+ 字号放大一号 + 撤掉 report 「更多」工具栏（删除已改走左滑）。CVM 8/8 backend pytest + client 548/548 jest + prod build all green |
| 2026-05-29 | **Phase B · M11-06 ✅**（教练定制课程）：`COACH_COURSE_USER_IDS` 白名单 + 写 API（CRUD lesson/publish/unpublish）；客户端 `coachCoursesService`；M8 认证/UI 挂 wait-for-triggers §2.16 |
| 2026-05-29 | **Phase B · M11-05 ✅**（证书/勋章）：`course_certificate_service` + `GET /users/me/certificates|course-stage`；考核升阶返回 `certificate`；客户端 `certificate.tsx` Canvas 合成 + 列表页勋章 |
| 2026-05-29 | **Phase A · M7-13 ✅**（多挥识别 W28-W29）：`multi_swing.py` 腕速窗口切分 + 试挥启发式 + 50122；`real_pipeline` full_swing 集成 `swing_candidates` / `selected_swing_index` / `engine_warnings`；6 例单测；UI + 缩略图挂 `wait-for-triggers` §2.15 |
| 2026-05-29 | **Phase C · M12-06 ✅**（每周精选 banner）：`GET /v1/pros/topics/current` + `seed_initial_weekly_topic`；`pages/pros/index` banner + `pages/pros/topic` |
| 2026-05-29 | **Phase C · M12-07 ✅**（PGC 解说 + LLM）：`GET /v1/pros/clips/{id}/annotations` + `POST .../pgc-insight` + `seed_initial_pgc_annotations`；`pages/pros/clip-insight` + 球手详情「解说」入口 |
| 2026-05-29 | **Phase C · M12-08 ✅**（追平演化动画）：`posInterpolate` + `SkeletonAnimation` + `pro-compare` 三态示意；demo clip `evolution_poses` seed；无 pose 时雷达 morph 降级 |
| 2026-05-29 | **Phase C · M12-09 ✅**（教练引用 pro_clip）：`analysis_annotations` + coach video_ref API；`ProClipPicker` / `ProClipReferenceCard` / `pages/coach/analysis-annotate` |
| 2026-05-29 | **Phase C · M12-10 ✅**（收藏 / 想试试看）：`user_pro_favorites.training_task_id` + favorites/try-it API；`proFavoritesService`；`clip-insight` 收藏+try-it；训练 Tab「对照球手训练」分组 |
| 2026-05-29 | **Phase D · M13-06 ✅**（约球风控）：`meetup_risk_service` + `user_credit_service` + Redis 日计数/冷却；42920/42921/40339；`users.meetup_credit_score` |
| 2026-05-29 | **Phase D · M13-07 ✅**（互评 + 信用）：`meetup_feedback_service` + feedback API + 24h 隔离；`pages/meetup/feedback`；Alembic 0029 唯一约束 |
| 2026-05-29 | **Phase D · M13-08 ✅**（挑战赛模板）：3 rule_template + events API + 排行 + honor badge；`pages/meetup/events/*`；Alembic 0030 `score_payload` |
| 2026-05-29 | **Phase D · M13-09 ✅**（合规）：TOS 强弹窗 + 40332/40333/40334 + gender_preference；Alembic 0031 用户实名字段 |
| 2026-05-29 | **Phase C · M12-05 ✅**（并排叠加+雷达）：`DualRadarChart` + `pages/analysis/pro-compare`；报告页 Top-1 匹配卡片与「职业对比」入口 |
| 2026-05-29 | **Phase C · M12-04 ✅**（和你最像匹配）：`pro_match_service` 启发式打分 + `GET /v1/analyses/{id}/pro-matches`；客户端 `prosService.matchForAnalysis()`；并排 UI 留 M12-05 |
| 2026-05-29 | W12-1/2/3 ✅（`8578cf6` + 测试 fix）：3 块按顺序连开。W12-1 progress API 把 `engine_version`+`analysis_confidence` 落到 `AnalysisProgressPoint`，客户端 ProgressLineChart 圆点按 trust tier mint/gold/warning 着色（V1 不上色保兼容），让"我的-成长曲线"也能看出哪几次是高/低可信。W12-2 把 P2-M7-04 早就落地的 `camera_angle.py` 真接入 `_enrich_v2` / `_enrich_v2_fallback`：偏角 >15° → `ANGLE_PENALTY_BAD=0.6` 真惩罚 confidence、`angle_engine_warnings` 追加 result.engine_warnings；`run_real_analysis_v2` 末尾改成"合并"而非"覆盖"避免 angle warning 被 probe/fallback 吞。W12-3 治理 MinIO ffprobe 5XX：5xx/timeout 指数退避 retry 2 次（4xx/binary_missing 立即放弃）、URL log 脱敏去 query string、失败不再静默而是返回 `probe_failed` engine_warning 让客户端 W10 调试浮层能直接看到原因；6 个新 metrics 分桶 (`v2_probe_retries` + `v2_probe_errors_{5xx/timeout}_after_retries` + `v2_probe_errors_{4xx/binary_missing/unknown}`)。CVM 11/11 backend + 93/93 ai_engine（W7+W8+W9 全回归 + W12-2/3 新单测 38 例）+ client 550/550 jest + prod build all green |
