# Drill 示范视频重建计划（一期 hotfix + 二期素材库）

> 版本：v0.1 · 2026-05-25
> 关联：
> - [`client/src/constants/drillVideoLibrary.ts`](../../client/src/constants/drillVideoLibrary.ts)
> - [`scripts/drill-demo-videos/manifest.json`](../../scripts/drill-demo-videos/manifest.json)
> - [`docs/21-二期产品需求规划.md`](../21-二期产品需求规划.md) §四 M7 / §五 M8 / §八 M11 / §九 M12
> - 体验版回归：[`docs/release-notes/experience-version-smoke-runbook.md`](experience-version-smoke-runbook.md)
> 状态：**hotfix 已落地** + 二期素材重建已纳入排期

---

## 一、问题与根因

### 1.1 用户反馈

> 「教练（AI 教练对话页）里引用的视频针对性不强，与文字描述内容不符合。」

### 1.2 根因（v1.1.1 遗留）

一期 W7 时为了让 AI 教练对话 / 训练计划 / 报告页有视频内容支撑，从 [Mixkit 免费高尔夫 stock 视频库](https://mixkit.co/free-stock-video/golf/) 挑了 13 段通用素材，按 `drill_id` 一一拼装到 `samples/drills/{drill_id}.mp4`。

但素材内容是泛高尔夫场景（爸爸教孩子打球 / 老年女性打球 / 女孩练球 / 推杆特写 …），**与对应 drill 的「name + steps」没有任何呼应**。

错配清单（**13 条全部不对应**）：

| drill_id | drill 文字描述（节选） | Mixkit 视频实际内容 | 错配度 |
|----------|---------------------|---------------------|--------|
| `drill_towel_arm` | 取一条小毛巾，折叠后**夹在双臂之间**做半挥杆 | 「A man teaching his son how to play golf」（父子教学场景） | ❌ |
| `drill_impact_bag` | 用半挥杆慢速**击打击球包** | 「Golf club hitting a ball on a golfing range」（练习场击球） | ❌ |
| `drill_half_swing` | **半挥杆**节奏：杆与地面平行后停住 | 「Girl hitting a golf ball」（女孩全挥击球） | ⚠️ 仅勉强相关 |
| `drill_inside_path` | 用**地面练习杆引导内侧下杆** | 「Girl practising golf」（女孩练球） | ❌ |
| `drill_wall_butt` | **臀部贴墙站立**做镜像挥杆 | 「Boy practising golf」（男孩练球） | ❌ |
| `drill_hip_rotation` | 球杆横放髋部前，**髋部以脊柱为轴旋转** | 「Senior female playing golf」（老年女性打球） | ❌ |
| `drill_mirror_spine` | **面对落地镜**观察脊柱角度 | 「Father teaching daughter to play golf」（父女教学） | ❌ |
| `drill_weight_shift` | 口令「后-前-收」练**重心转移** | 「People playing Golf」（一群人打球） | ❌ |
| `drill_backswing_stop` | **上杆到杆接近水平就停 2 秒** | 「Little brothers playing golf」（兄弟打球） | ❌ |
| `drill_shoulder_turn` | 双手抱肩，旋转直到**左肩触下巴** | 「Young girl playing golf」（年轻女孩打球） | ❌ |
| `drill_plane_board` | 斜放练习板，杆头沿板面**挥杆平面**移动 | 「Golfers in a line」（一排人打球） | ❌ |
| `drill_alignment_stick` | 地上放**瞄准杆**对齐目标 | 「Girl pics a golf ball from the hole」（女孩从洞里捡球） | ❌ 连主题都不对 |
| `drill_grip_checkpoint` | 标准**握杆**法：看到 2-3 颗指关节 | 「Close up of a golf club putting a golf ball」（推杆击球特写） | ❌ |

> 代码里其实早已意识到（`drillVideoLibrary.ts` 老注释 `素材为通用参考片段，非专属教程` + `VideoCard.tsx` 底部老 hint 「开源高尔夫素材示范，专属教学片陆续更新」），但未做隔离处理，用户层面仍能看到错配视频卡片，反而比"暂时没有视频"更糟。

---

## 二、Hotfix（已落地）

> 目标：**先止血** —— 把会误导用户的视频卡片全部下架，等专属素材重建上线再恢复。

### 2.1 改动点

| 文件 | 变化 |
|------|------|
| [`client/src/constants/drillVideoLibrary.ts`](../../client/src/constants/drillVideoLibrary.ts) | 新增白名单常量 `DRILL_VIDEO_ALIGNED_IDS`，**当前为空**；老常量 `DRILL_VIDEO_IDS` 保留为 alias 防外部 TS 编译断裂；title 后缀由 `· 动作参考` 改为 `· 教练示范`；JSDoc 完整记录 hotfix 来龙去脉 |
| [`client/src/components/VideoCard.tsx`](../../client/src/components/VideoCard.tsx) | 底部 hint 由「开源高尔夫素材示范，专属教学片陆续更新」改为「动作示范片段，请配合文字步骤练习」 |
| [`client/src/utils/__tests__/drillVideoLibrary.test.ts`](../../client/src/utils/__tests__/drillVideoLibrary.test.ts) | 重写为「未对齐 drill_id 返回 null + 用户直传 video_url 仍可解析」契约 |
| [`client/src/components/__tests__/VideoCard.test.ts`](../../client/src/components/__tests__/VideoCard.test.ts) | 同步契约：未对齐 drill_id 不再返回 stock 素材 |
| [`scripts/drill-demo-videos/manifest.json`](../../scripts/drill-demo-videos/manifest.json) | 顶部加 `status: "quarantined"` + `alignment_with_drill_steps: "all_misaligned"` 状态标记 |

### 2.2 联动效果（**前端单点改 = 全链路下线**）

| 渲染点 | 改动前 | 改动后 |
|--------|--------|--------|
| **AI 教练对话页**（`pages/coach/index.tsx`） | 命中 drill 关键词后 chat_service 自动附 `video_card` → 渲染 Mixkit 错配视频 | 后端仍附 `video_card` attachment，但前端 `VideoCard` 因 `resolveVideoCardDetail` 返回 null 而 `return null` → 视频卡片**不渲染**，drill_card 文字步骤仍正常展示 |
| **训练计划页**（`pages/training/index.tsx`） | 任务展开后 `getDrillVideoDetail(task.drill_id)` 拿到 stock 视频对象 → 渲染 | `getDrillVideoDetail` 返回 null → `{drillVideo && <VideoCard … />}` 短路，**整块视频区域消失**，文字步骤照常 |
| **分析报告页 drill 卡片** | 同上链路 | 同上 |
| **教练 / 用户上传自定义视频**（M8 / M12 未来场景） | 走 attachment.video_url 直传 → 不受 drillVideoLibrary 影响 | **保持可用**（测试已校验） |

### 2.3 后端契约保持不变

- `chat_service._video_cards_for_drills()` 仍然按 heuristic 生成 `video_card` attachment（只带 drill_id + title）
- 落库的消息结构、API schema、SSE 流不动
- 前端做最末端的「白名单过滤 + graceful null」，后端 / 数据库 / Celery 任务零改动 → 极低破坏性

> ⚠️ **二期重启坑位（必看）**：当前 `_video_cards_for_drills()` 拼的 title 后缀是 `· 动作参考`（[`backend/app/services/chat_service.py`](../../backend/app/services/chat_service.py) L325），而前端 `DRILL_VIDEO_TITLE_SUFFIX = ' · 教练示范'`（[`client/src/constants/drillVideoLibrary.ts`](../../client/src/constants/drillVideoLibrary.ts) L63）。`resolveVideoCardDetail` 取 `title: input.title || base.title` ⇒ 二期 `DRILL_VIDEO_ALIGNED_IDS` 重新填值后，后端 title 会**覆盖**前端 suffix，最终展示「{name} · 动作参考」，与新视觉文案不一致。`P2-M7-N1` 重建素材库前请同步把后端 suffix 改为 `· 教练示范`（或一次性改成「后端只传 drill_id，title 全由前端 base.title 生成」更干净）。已加入 §四 D-6。

### 2.4 验收清单（hotfix）

- [x] `pnpm type-check` 通过
- [x] `pnpm test client/src/utils/__tests__/drillVideoLibrary.test.ts` 通过
- [x] `pnpm test client/src/components/__tests__/VideoCard.test.ts` 通过
- [ ] 真机回归：AI 教练对话发送「我下杆抛杆」→ 不应出现视频卡片，drill_card 文字步骤仍展示
- [ ] 真机回归：训练计划展开任意任务 → 不应出现视频区域，文字步骤仍展示
- [ ] 真机回归：分析报告页 drill 卡片展开 → 不应出现视频区域

> 真机回归归入下次体验版 Smoke（详 [`docs/release-notes/experience-version-smoke-runbook.md`](experience-version-smoke-runbook.md)）。

---

## 三、二期专属素材重建方案

> 目标：**13 个 drill 各自有 1 段 30-60s 的专属示范片**，内容与文字步骤一一呼应，并具备扩展到 M11 课程体系 / M12 职业球手对比库 / M8 教练 PGC 内容生产线的基础设施。

### 3.1 方案选型

| 方案 | 评估 | 决定 |
|------|------|------|
| **A · 自建拍摄团队 + 签约教练录制** | ✓ 控制力最强（版权 / 画质 / 风格统一） ✓ 与白皮书 §7.2 视觉规范完美对齐 ✓ 同一套团队复用 M11 课程视频 / M12 职业对比专题 / M8 教练 PGC ✗ 启动成本 + 周期 | **选 ✓** |
| B · 引用 B 站 / 抖音教学博主公开视频 | ✓ 素材丰富 ✗ 微信小程序不允许内嵌第三方播放器 ✗ 版权与博主合作流程复杂 ✗ 画质 / 风格难统一 | 否 |
| C · YouTube 公开教学视频 | ✗ 国内访问不稳定 ✗ 微信生态合规风险 | 否 |
| D · 用户 / 教练 UGC 自传 | ✓ 长期可持续 ✗ 冷启阶段没有种子内容 | 作为 A 的**补充**（M8 教练工作台上线后开 |

### 3.2 素材规格（与白皮书 §7.2 视觉规范对齐）

| 维度 | 规格 |
|------|------|
| 时长 | 30-60s（关键动作 ≤ 45s，含 5s 片头 + 5s 字幕落版） |
| 比例 | **竖屏 9:16**（适配小程序 Video 组件主播放场景） |
| 分辨率 | 1080×1920（H.264 yuv420p，目标 < 8 MB） |
| 帧率 | 30fps |
| 片头 | 0-3s 灵鸟金色 logo + drill 中文名（字号 / 字体 / 配色按 `client/src/app.scss` 变量） |
| 主体 | 教练全身镜（face_on 或 dtl 视角，与该 drill 适合的机位一致） + 关键步骤口播字幕 |
| 片尾 | 末 5s 字幕「按文字步骤练习更精确，记得拍挥杆来 AI 复盘」+ 弱化品牌水印 |
| 字幕 | 中文简体，白底冷靛蓝（`--color-primary` `#1a237e`）描边；底部安全区 ≥ 90px 避免被 UI 遮挡 |
| 音频 | 立体声 AAC 128kbps；教练标准普通话口播；背景音乐音量 ≤ -18dB |
| 封面 | 1080×1920 + 1080×1080 两版，分别用于竖屏播放 poster 与方形卡片 |

### 3.3 拍摄清单（13 段）

| # | drill_id | 适合机位 | 道具 | 关键镜头 |
|---|----------|---------|------|---------|
| 1 | drill_towel_arm | face_on | 小毛巾 | 教练夹毛巾做半挥；特写双臂连接感 |
| 2 | drill_impact_bag | dtl | 击球包 | 半挥慢速击包；杆头贴身体特写 |
| 3 | drill_half_swing | face_on | 7 号铁 | 上杆到杆水平 → 停顿 → 缓慢下杆 |
| 4 | drill_inside_path | dtl | 练习杆 × 2 | 球后 30cm 放杆；下杆从内侧通过 |
| 5 | drill_wall_butt | face_on | 室内墙 | 背墙站立；上下杆全程臀部不离墙 |
| 6 | drill_hip_rotation | face_on | 球杆 × 1 | 杆横放髋前；缓慢左右髋转 |
| 7 | drill_mirror_spine | dtl | 落地镜 | 镜前空挥；setup → impact 脊柱角对比 |
| 8 | drill_weight_shift | face_on | — | 口令配挥杆；收杆 80% 重心在前脚 |
| 9 | drill_backswing_stop | face_on | — | 上杆到水平停 2 秒；肩转 90° 校验 |
| 10 | drill_shoulder_turn | face_on | — | 抱肩旋转；左肩触下巴 |
| 11 | drill_plane_board | dtl | 练习板 / 厚枕头 | 斜板辅助；杆头沿板面 |
| 12 | drill_alignment_stick | face_on（俯仰对比） | 瞄准杆 × 2 | 地面瞄准杆指向目标；双脚 / 双膝 / 肩线对齐 |
| 13 | drill_grip_checkpoint | 双手特写 | — | 左手看到 2-3 颗指关节；右手 V 字指向右肩 |

### 3.4 成本估算

| 项 | 单价 | 数量 | 小计 |
|----|------|------|------|
| 教练出镜（签约 1-2 位 PGA / 大区教练） | ¥800-1500 / 天 | 2 天（13 段一次性拍完） | ¥1.6K-3K |
| 拍摄团队（1 摄 + 1 灯光 / 收音） | ¥2000-3500 / 天 | 2 天 | ¥4K-7K |
| 后期剪辑（13 段统一片头 / 字幕 / 调色） | ¥300-500 / 段 | 13 段 | ¥4K-6.5K |
| 室内场地（含落地镜 / 击球包等道具） | ¥800 / 天 | 2 天 | ¥1.6K |
| **合计** | | | **¥11K-18K** |

### 3.5 排期（与 [`docs/21`](../21-二期产品需求规划.md) §十五 联动）

| Phase | 周次 | 动作 |
|-------|------|------|
| **Phase 2.0**（评审 / 设计） | W14 | 教练初选 / 签约 / 拍摄脚本（按 §3.3 清单）/ 场地预约 |
| **Phase 2.1**（引擎地基） | W15 | 拍摄 2 天 + 后期 1 周 → 13 段成片就绪 |
| **Phase 2.1**（引擎地基） | W16 | 上传 MinIO `samples/drills/{drill_id}.mp4` + 海报 → 把 13 个 drill_id 加入 `DRILL_VIDEO_ALIGNED_IDS` → 灰度 5% |
| **Phase 2.1 收尾** | W17 | 全量灰度；体验版 Smoke 回归 |

### 3.6 长期：素材生产工厂

> 同一套拍摄 + 后期能力会被 M12 / M11 / M8 反复用：

| 模块 | 同一套素材生产能力的复用 |
|------|------------------------|
| M11 课程体系 | 7 阶段 × 5-10 节 ≈ 40-60 段微课视频 |
| M12 职业球手对比库 | 每位球手 ≥3 条解说视频 × 10-20 位 ≈ 30-60 段 |
| M8 教练工作台 | 教练 PGC 上传走同一套规格 / 审核流 |

→ 建议二期固定签约 1 个教练 + 1 个拍摄 / 后期外包，按月或按 milestone 结算（与白皮书 §6 商业模型对齐）。

---

## 四、关键决策记录

| # | 决策 | 时间 | 理由 |
|---|------|------|------|
| D-1 | hotfix 选**前端 disable**而非删除 Mixkit 视频文件 | 2026-05-25 | 改动量最小 + 后端契约不动 + 用户直传场景不受影响 |
| D-2 | 老常量 `DRILL_VIDEO_IDS` 保留为 alias | 2026-05-25 | 避免外部消费方瞬间 TS 编译失败；下个版本迭代时可逐步迁移 |
| D-3 | 不删除 `scripts/drill-demo-videos/manifest.json` | 2026-05-25 | 留作历史记录 + 同步脚本未来仍可能复用；用 status 字段隔离即可 |
| D-4 | 13 段专属素材纳入 **Phase 2.1**（与 M7 引擎地基同期）而非 Phase 2.4（产品包装） | 2026-05-25 | 教练对话 / 训练计划 / 报告页是一期已上线核心闭环，越早恢复视频补全越能挽回 NPS |
| D-5 | 拍摄成本控制在 ¥11K-18K（不超 ¥20K） | 2026-05-25 | 与 docs/21 §十三 商业模式约束一致（二期不铺重资产） |
| D-6 | 后端 `_video_cards_for_drills()` title 后缀**暂不改**，但在二期重建素材库前**必须**改为 `· 教练示范`（或彻底改为「后端只传 drill_id，title 全由前端生成」） | 2026-05-25 | 当前 `DRILL_VIDEO_ALIGNED_IDS` 为空 → 前端拿 video_card 必定 null，文案分裂对用户不可见；改后端要带回归测试 + 后端单测（`tests/services/test_chat_reply_attachments.py`），单纯为「不可见的将来场景」改动得不偿失。**P2-M7-N1 启动时同步处理**。 |

---

## 五、变更记录

| 日期 | 版本 | 说明 |
|------|------|------|
| 2026-05-25 | v0.1 | 初版：诊断 / hotfix / 二期专属素材库重建方案 / 排期 / 成本 |
| 2026-05-25 | v0.1.1 | review 补漏：§2.3 加二期重启坑位提示（后端 / 前端 title 后缀分裂）+ §四 加 D-6 决策；顺手修 `client/src/components/VideoCard.tsx` 一期遗留 TS bug（`<Video showLoading>` 非法 prop，Taro 运行时本就忽略，删除即可消除 type-check 噪音）；给 [`docs/release-notes/o-07-skeleton-fps-smoke-runbook.md`](o-07-skeleton-fps-smoke-runbook.md) §2 步骤 8 加 hotfix 期预期注 |
