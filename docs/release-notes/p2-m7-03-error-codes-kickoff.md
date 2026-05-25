# P2-M7-03 · 错误码扩展 · 启动包（W18 起跑）

> 版本：v0.1（2026-05-25）
> 状态：启动输入稿
> 适用范围：二期 Phase 2.1 期间，将 AI 引擎错误码从 50100-50105 扩展到 20+，并完成三端（engine / backend / client）文案闭环
> 上游真源（待 PR #20 合并后生效）：[`docs/23 §3.3 · P2-M7-03 · 错误码扩展`](../23-二期可编码规格说明书.md#33-p2-m7-03--错误码扩展从-50100-50105-扩到-20)
> 前置 kickoff：[`p2-m7-02-video-reader-enhancement-kickoff.md`](./p2-m7-02-video-reader-enhancement-kickoff.md)（§3.1 定义 `50120 DecodeError` engine 侧抛码；**本任务收口客户端文案 + 全表注册**）

---

## 一、文档目的与边界

### 1.1 目的

为 **P2-M7-03 错误码扩展**落地一份「**W18 即可起跑、W21 三端文案 100% 覆盖**」的工程启动 SOP，让 AI 工程 + 客户端 + 后端明确：

- 一期 50100-50105 的现状与痛点（**50102 过于笼统**、50101 混载下载/解码）
- v0.1 错误码全表（50106-50123，**18 个新增码** + 一期 6 个保留码 = 24 个引擎码）
- 三端改动文件清单与 PR 切分策略
- `POST /precheck` 早失败映射（FR-4）
- 单测 / CI 门禁（AC-2：缺文案 PR 阻断）
- W18-W21 周计划

### 1.2 边界（**不**做项）

| 不做 | 原因 |
| --- | --- |
| 不修改 docs/22 / docs/23 / docs/20 任何字段 | 避免与 #18 / #19 / #20 race；本文件只引用 |
| 不实现 M7-02 解码逻辑 | 50120 engine 抛码归 P2-M7-02；本任务只注册 + 客户端文案 |
| 不实现 M7-07 多挥杆 / M10 mode 业务逻辑 | 50122 / 50123 先**占位注册 + 文案**，业务触发由各任务 PR 接入 |
| 不改 waiting 页 UI 结构 | 复用一期 `describeAnalysisFailure`；不新增 ErrorState 组件（P2-M0-01 backlog） |
| 不收紧一期错误码 | docs/23 灰度规约：仅扩展不收紧；50102 保留为**兼容兜底** |

### 1.3 与其他文档的关系

```
docs/23 §3.3          ← 需求真源（FR / AC / NFR / 灰度）
  ↑ 1:1 引用
本文件                 ← 错误码 v0.1 全表 + 三端改动 SOP
  ↓ W21 回流到
docs/02 §11.1（拟）   ← 错误码终稿表（enum + 触发 + 文案）
docs/01 §4.4（拟）    ← 视频质量检测二期增量提示
client/.../analysisEngineErrors.ts  ← 客户端文案真源
ai_engine/app/errors.py               ← 异常类 + code 真源
```

> **与 P2-M7-02 分工**：M7-02 §3.1 约定 `50120` engine 抛码 + backend 退配额；**50120 客户端文案由本任务（M7-03）收口**，避免 M7-02 PR 越界改 client。

---

## 二、现状盘点

### 2.1 错误码传播链路

```
ai_engine/app/errors.py          PipelineError 子类 (.code / .user_message)
  ↓ POST /analyze 或 /precheck
ai_engine/app/main.py            AnalyzeResult / PrecheckResult (error_code, error_message)
  ↓ HTTP 200 + body
backend/app/tasks/analysis_tasks.py   透传 50100-50199 → swing_analyses.error_code
  ↓ GET /v1/analyses/{id}/status
client/.../analysisEngineErrors.ts    describeAnalysisFailure(code) → title / hint / reshootRecommended
  ↓
client/pages/analysis/waiting.tsx     等待页 / 历史失败态展示
```

### 2.2 一期已有（保留，不删）

| 码 | 类 / 场景 | engine | client 文案 | 问题 |
| --- | --- | --- | --- | --- |
| 50100 | transport（backend→engine 不可达） | backend 生成 | ✅ | — |
| 50101 | `PreprocessError`（下载 / ffprobe / 通用预处理） | ✅ | ✅ | 与 codec 失败混载；M7-02 拆出 50120 |
| 50102 | `PoorQualityError`（**所有**画质硬门槛） | ✅ | ✅ | **过于笼统**：暗光 / 抖动 / 清晰度不稳定共用一码 |
| 50103 | `NoPersonError` | ✅ | ✅ | — |
| 50104 | `NoSwingError` | ✅ | ✅ | — |
| 50105 | `PoseModelError` | ✅ | ✅ | — |

### 2.3 关键文件

| 文件 | 现状 | M7-03 改造 |
| --- | --- | --- |
| `ai_engine/app/errors.py` | 5 个业务异常类 | 新增 12+ 子类；50102 保留作兜底 |
| `ai_engine/app/pipeline/preprocess.py` | 全抛 `PoorQualityError` / `PreprocessError` | 按 §5.1 映射表抛细分码 |
| `ai_engine/app/pipeline/precheck.py` | 共用 `enforce_quality_gates` | 同上映射；FR-4 早失败 |
| `ai_engine/tests/test_errors.py` | 断言 50101-50105 | 扩到全表 + registry 单测 |
| `backend/app/tasks/analysis_tasks.py` | 50100-50199 透传 + 退配额 | 注释更新；确认 50106+ 退配额 |
| `client/src/constants/analysisEngineErrors.ts` | 仅 50101-50105 | 扩到 50106-50123；fallback 对齐 docs/23 |
| `client/src/constants/__tests__/analysisEngineErrors.test.ts` | 6 个用例 | 每码至少 1 用例 + registry 完整性测试 |

### 2.4 已知缺口（vs docs/23 §3.3 FR）

| FR | 现状 | 缺口 |
| --- | --- | --- |
| FR-1 新增 ≥15 码 | 仅 50101-50105 | 缺 50106-50123（本文件 §3 全表） |
| FR-2 enum + 文案 + 重拍建议 + 严重度 | 一期无 enum | §3 码表 + `errors.py` 类名 |
| FR-3 客户端 100% 覆盖 | 仅 5 码 | 扩 `analysisEngineErrors.ts` + CI 门禁 |
| FR-4 precheck 早失败 | precheck 已跑质量门，但全返 50102 | 按 §5.1 细分 error_code |

---

## 三、错误码 v0.1 全表（W18 冻结）

> **规约**（docs/23 §11.4）：50106-50123 为 M7 V2 引擎扩展段；W21 PR 合入时回流 docs/02 §11.1，本节改 `superseded`。

### 3.1 新增码（50106-50123，共 18 个）

| 码 | enum | 异常类 | 严重度 | 触发条件 | precheck | 用户 title（≤30 字） | 如何重拍（≤80 字） |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 50106 | `VIDEO_TOO_SHORT` | `VideoTooShortError` | fatal | `duration < MIN_DURATION_SEC` | ✅ | 视频时长过短 | 挥杆视频至少拍 3 秒，请包含完整上杆到收杆后再上传。 |
| 50107 | `VIDEO_TOO_LONG` | `VideoTooLongError` | fatal | `duration > MAX_DURATION_SEC` | ✅ | 视频时长过长 | 单段挥杆请控制在 30 秒以内，只拍一次挥杆动作即可。 |
| 50108 | `RESOLUTION_TOO_LOW` | `ResolutionTooLowError` | fatal | 短边 < 720（V2 分层阈值） | ✅ | 视频分辨率过低 | 请在手机设置中选 1080p 及以上，并确保球员清晰占画面 1/2 以上。 |
| 50109 | `LOW_LIGHT` | `LowLightError` | fatal | `clarity_score < MIN_CLARITY` | ✅ | 光线不足 | 请在光线充足的练习场或户外重拍，避免逆光与强阴影。 |
| 50110 | `CAMERA_SHAKE` | `CameraShakeError` | fatal | `stability_score < MIN_STABILITY_HARD_BLOCK` | ✅ | 画面抖动过大 | 请固定手机或使用三脚架，拍摄时避免手持晃动。 |
| 50111 | `UNSTABLE_CLARITY` | `UnstableClarityError` | fatal | `low_clarity_frame_ratio > 阈值` | ✅ | 清晰度不稳定 | 拍摄时保持对焦清晰，避免半清晰半模糊；擦净镜头后重拍。 |
| 50112 | `COMPOSITE_QUALITY_LOW` | `CompositeQualityError` | fatal | `quality_score < MIN_QUALITY_SCORE`（综合分） | ✅ | 视频质量未达标 | 请改善光线、稳定机位并确保全身入镜后重新拍摄。 |
| 50113 | `PARTIAL_BODY` | `PartialBodyError` | fatal | 关键点可见性不足 / 半身入镜（AC-3） | analyze | 人物未完整入镜 | 请退后 2-3 米，确保头到脚完整出现在画面中再拍。 |
| 50114 | `LOW_POSE_CONFIDENCE` | `LowPoseConfidenceError` | warn | pose 有效帧占比偏低但未达 NoPerson | analyze | 动作识别置信度偏低 | 请穿与背景对比明显的服装，避免遮挡，在简洁背景下重拍。 |
| 50115 | `FRAME_DECODE_LOSS` | `FrameDecodeLossError` | fatal | `frame_loss_ratio > 阈值` | ✅ | 视频解码异常 | 请重新导出或另存视频后再上传；避免使用损坏的文件。 |
| 50116 | `KEYPOINT_MISSING` | `KeypointMissingError` | fatal | 关键帧肩/髋/腕 visibility 持续缺失 | analyze | 关键动作无法识别 | 请确保侧向或正对机位，球员不要被球包/他人遮挡。 |
| 50117 | `ORIENTATION_UNSUPPORTED` | `OrientationUnsupportedError` | fatal | 极端竖屏 / 旋转元数据异常 | ✅ | 视频方向异常 | 请在系统相机中关闭异常旋转，竖屏正常握持拍摄。 |
| 50118 | `ANALYSIS_TIMEOUT` | `AnalysisTimeoutError` | fatal | pipeline 总耗时超 SLA | analyze | 分析超时 | 请缩短视频时长或稍后重试；持续出现请联系客服。 |
| 50119 | `ENGINE_OVERLOAD` | `EngineOverloadError` | fatal | 队列积压 / 并发超限（运维触发） | — | 服务繁忙 | 当前分析人数较多，请稍后再试。 |
| 50120 | `DECODE_UNSUPPORTED` | `DecodeError` | fatal | HEVC/HDR/VP9 转码失败（M7-02） | ✅ | 视频格式暂不支持 | 请在相机设置中选「兼容性最佳」或 H.264 格式后重拍。 |
| 50121 | `SLOWMO_METADATA_FAILED` | `SlowmoMetadataError` | fatal | mov 慢动作元数据无法解析（M7-02） | ✅ | 慢动作格式无法识别 | 请用普通模式拍摄，或在相册中「转换为兼容格式」后再上传。 |
| 50122 | `MULTI_SWING_OVERFLOW` | `MultiSwingOverflowError` | fatal | 检测到 >5 段挥杆候选（M7-07） | analyze | 检测到多次挥杆 | 请每段视频只拍一次挥杆，或剪辑掉多余动作后再上传。 |
| 50123 | `MODE_CLUB_MISMATCH` | `ModeClubMismatchError` | fatal | mode 与 club_type 不匹配（M10） | analyze | 模式与球杆不匹配 | 推杆分析请选择推杆模式；全挥杆请勿选推杆。 |

### 3.2 一期保留码（50101-50105，兼容兜底）

| 码 | 保留策略 |
| --- | --- |
| 50101 | **收窄**：仅 curl 下载失败 / ffprobe 无法读 / 容器损坏；不再用于 codec 失败 |
| 50102 | **保留作兜底**：无法归类到 50109-50112 的画质失败仍走 50102，灰度期日志告警 |
| 50103-50105 | 不变 |

### 3.3 统计

| 类别 | 数量 |
| --- | --- |
| 一期保留（50100-50105） | 6 |
| 新增（50106-50123） | 18 |
| **引擎码合计** | **24**（≥ docs/23 AC-1 要求的 20） |

### 3.4 AC-3 真机回归四场景映射

| 故意拍摄场景 | 期望命中码 | 验证点 |
| --- | --- | --- |
| 3 秒以下短视频 | **50106** | precheck blocked + 客户端 title「视频时长过短」 |
| 暗光环境 | **50109** | precheck blocked + hint 含「光线」 |
| 手持剧烈抖动 | **50110** | precheck blocked + hint 含「三脚架」 |
| 半身 / 裁切球员 | **50113** | analyze failed + hint 含「完整入镜」 |

---

## 四、三端改动清单

### 4.1 AI Engine（Owner：AI 工程）

| 改动 | 文件 | 工程量 |
| --- | --- | --- |
| 新增 18 个异常类 + registry | `ai_engine/app/errors.py` | 1 PD |
| `enforce_quality_gates` 按 §3.1 抛细分码 | `preprocess.py` | 1.5 PD |
| precheck 透传细分码 | `precheck.py`（几乎不动，继承 preprocess 映射） | 0.5 PD |
| registry 单测 + 映射单测 | `tests/test_errors.py` + `tests/test_preprocess.py` | 1 PD |

### 4.2 Backend（Owner：AI 工程 / 后端）

| 改动 | 文件 | 工程量 |
| --- | --- | --- |
| 确认 50106-50123 透传 + 退配额 | `analysis_tasks.py` L195 已支持 50100-50199；补注释 + 单测 | 0.5 PD |
| precheck 失败 early exit 透传新码 | `analysis_tasks.py` L141-146 | 0.5 PD |

### 4.3 Client（Owner：客户端）

| 改动 | 文件 | 工程量 |
| --- | --- | --- |
| `ENGINE_FAILURE_COPY` 扩到 50106-50123 | `analysisEngineErrors.ts` | 1.5 PD |
| fallback 对齐 docs/23：`服务暂时不可用，请稍后再试` | 同上 `GENERIC_FAILURE` | 0.5 PD |
| 每码单测 + registry 完整性 | `__tests__/analysisEngineErrors.test.ts` | 1 PD |
| precheck blocked 态展示新码文案 | `waiting.tsx`（已通过 `describeAnalysisFailure`，无需改结构） | 0 PD |

**合计：~8 PD**（与 docs/23 §3.3 估时 2 PW 一致）

### 4.4 推荐 PR 切分（3 个 PR，可并行 review）

| PR | 内容 | 依赖 |
| --- | --- | --- |
| **PR-A** engine | `errors.py` + `preprocess.py` 映射 + engine 单测 | M7-02 50120 类已合入 |
| **PR-B** client | `analysisEngineErrors.ts` + 单测 + CI 门禁 | 可与 PR-A 并行（按 §3 文案写死） |
| **PR-C** docs | 回流 docs/02 §11.1 + docs/01 §4.4 增量 | PR-A + PR-B 合入后 |

---

## 五、precheck 早失败映射（FR-4）

### 5.1 `enforce_quality_gates` → error_code 映射表

| preprocess 检查 | 现抛 | V2 抛 | precheck |
| --- | --- | --- | --- |
| `duration < MIN` | `PreprocessError`(50101) | **50106** | ✅ |
| `duration > MAX` | `PreprocessError`(50101) | **50107** | ✅ |
| 短边 < 720 | （未单独检查） | **50108** | ✅ 新增 gate |
| `clarity < MIN` | `PoorQualityError`(50102) | **50109** | ✅ |
| `stability < HARD_BLOCK` | `PoorQualityError`(50102) | **50110** | ✅ |
| `low_clarity_ratio > 阈值` | `PoorQualityError`(50102) | **50111** | ✅ |
| `quality_score < MIN` | `PoorQualityError`(50102) | **50112** | ✅ |
| `frame_loss > 阈值` | `PoorQualityError`(50102) | **50115** | ✅ |
| ffmpeg codec 失败 | `PreprocessError`(50101) | **50120** | ✅ M7-02 |
| 慢动作元数据失败 | — | **50121** | ✅ M7-02 |

> **50102 兜底**：映射逻辑未覆盖的 `PoorQualityError` 仍返 50102，Sentry 打点 `unmapped_quality_gate` 供 W19 迭代消减。

### 5.2 早失败收益指标

- W21 上线后对比：完整 `POST /analyze` 调用中 **因画质/时长在 precheck 被 blocked 的占比** ≥ 60%（减少无效 pose 推理 CPU）

---

## 六、单测 / CI 门禁

### 6.1 Engine：`tests/test_error_registry.py`（新增）

```python
# 所有 50106-50123 必须在 ERROR_REGISTRY 有 entry
EXPECTED_CODES = list(range(50106, 50124))

def test_all_v2_codes_registered():
    from app.errors import ERROR_REGISTRY
    for code in EXPECTED_CODES:
        assert code in ERROR_REGISTRY
        assert ERROR_REGISTRY[code].user_message  # 中文文案非空
```

### 6.2 Client：registry 完整性测试

```typescript
// analysisEngineErrors.test.ts
const V2_CODES = [50106, 50107, /* ... */, 50123]

test.each(V2_CODES)('码 %i 必须有 ENGINE_FAILURE_COPY 条目', (code) => {
  const r = describeAnalysisFailure({ code, message: '' })
  expect(r.title).not.toBe('分析失败') // 不能落 GENERIC_FAILURE
  expect(r.hint).toBeTruthy()
})
```

### 6.3 CI 门禁（W19 接入）

- `make client-test`：`analysisEngineErrors.test.ts` 100% 覆盖 §3.1 全表
- `make backend-test`：`test_analysis_stage_and_errors.py` 扩 parametrize 到 50106+
- **PR 模板新增 checkbox**：`[ ] 新增 error_code 已同步 analysisEngineErrors.ts`

---

## 七、W18-W21 周计划

> **前置**：P2-M7-02 W17 完工（50120/50121 engine 抛码就绪）。本任务 W18 起跑。

| 周 | 任务 | DoD |
| --- | --- | --- |
| **W18** | 本文件评审；AI 工程出 `errors.py` registry PoC + §3 码表 freeze | ☑ §3 码表 PM/AI Lead 签字；☑ registry PoC 单测绿 |
| **W19** | PR-A engine：`preprocess.py` 映射 + precheck 细分码；PR-B client 文案并行 | ☑ 50106-50115 precheck 单测全绿；☑ client registry 测试全绿 |
| **W20** | PR-A 合入；50120-50121 与 M7-02 联调；50122/50123 占位注册 | ☑ AC-3 四场景真机回归通过；☑ 50120 客户端文案可见 |
| **W21** | PR-C docs 回流；灰度 3 天 Sentry 观测；全量开用户文案 | ☑ AC-1/2/3 达成；☑ docs/02 §11.1 合入；☑ 本文件 `superseded` |

---

## 八、责任 / 风险 / 验收

### 8.1 责任

| 角色 | 责任 |
| --- | --- |
| AI 工程 Lead | 总 owner；engine registry + preprocess 映射 + engine 单测 |
| 客户端 | `analysisEngineErrors.ts` 全表 + 单测 + waiting 页验收 |
| 后端 | precheck 透传确认 + 退配额单测 |
| PM | W18 码表 freeze 守门；W21 AC 签字 |

### 8.2 风险

| ID | 风险 | 兜底 |
| --- | --- | --- |
| R-01 | M7-02 延期导致 50120/50121 无法联调 | W19 先用 stub 类占位；W20 联调 |
| R-02 | 50102 与细分码并存，前端仍收到旧码 | 灰度期 Sentry 监控 50102 占比；目标 W21 前 < 5% |
| R-03 | 文案超 NFR（title > 30 字） | W18 码表 review 时逐条计数；CI 可选 lint |

### 8.3 AC 兜底（复述 docs/23 §3.3）

- [ ] **AC-1**：错误码总数 ≥20；每个码都有中文文案 + 重拍建议
- [ ] **AC-2**：客户端 `analysisEngineErrors.ts` 100% 覆盖；缺文案 PR 阻断
- [ ] **AC-3**：真机回归 3s / 暗光 / 抖动 / 半身 4 场景各命中 1 码且文案可读

---

## 九、附录

### 9.1 与一期 50102 文案对照（50109 示例）

| 维度 | 一期 50102 | 二期 50109 |
| --- | --- | --- |
| title | 视频画质未达标 | 光线不足 |
| hint | 光线 + 侧向 + 擦镜头（混合） | 仅聚焦光线 |
| 用户感知 | 「不知道具体哪里不对」 | 「明确是光线问题」 |

### 9.2 灰度策略（docs/23 §3.3 + §11.3）

1. **W20-W21**：新码 Sentry + log 先行，用户仍看后端 `error_message` 原文
2. **W21 Day 4 起**：`describeAnalysisFailure` 对 50106+ 走 `ENGINE_FAILURE_COPY` 预设文案
3. **回滚**：关闭 feature flag `phase2_granular_error_codes` → 全部 fallback 50102 文案

### 9.3 50122 / 50123 占位说明

| 码 | 业务 owner | M7-03 职责 |
| --- | --- | --- |
| 50122 | P2-M7-07 阶段分割 V2 | 仅注册类 + 客户端文案；触发逻辑不在本任务 |
| 50123 | P2-M10-01 推杆模式 | 同上 |

---

## 十、变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-05-25 | 初版；50106-50123 全表 + 三端改动 + W18-W21 周计划 |
| v0.2 | W21 收尾 | AC 达成、`superseded` 标记、回流 docs/02 §11.1 后删 §3 码表 |
