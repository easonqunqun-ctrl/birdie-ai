# P2-M7-01 · ECS v2 标定集采集启动包

> 版本：v0.1（启动输入稿）
> 日期：2026-05-25
> 关联：
> - 任务规格真源：[`docs/23 §3.1 P2-M7-01`](../23-二期可编码规格说明书.md)（评审中, 见 PR #20）
> - 前置依赖：[`docs/22 §四`](../22-二期开发迭代计划.md)  **DEP-01**（4 周 30+ 段第一批）+ **DEP-02**（5-10 位教练签约）+ **DEP-04**（M12 球手版权梳理, 与本任务素材可复用一部分）
> - 产品力主线：[`docs/20 §五`](../20-AI引擎产品力迭代设计.md#五世界顶尖样本标定集elite-calibration-set-ecs) 世界顶尖样本标定集（Elite Calibration Set, ECS）
> - AI 引擎规格：[`docs/05 §八`](../05-AI模型技术规格文档.md) 二期 AI 引擎 V2 技术规格增量
> - 数据安全与法务：[`docs/06 §十三`](../06-数据安全与隐私合规文档.md) 二期隐私 / 合规增量
> - 排期：[`docs/22 §二`](../22-二期开发迭代计划.md) Phase 2.0 W14-W16（评审 + 启动）→ Phase 2.1 W17 起持续扩容到 ≥80 段
>
> **状态**：启动输入稿。**不阻塞 docs/22 / docs/23 评审**；W14 开会当天即可启动「教练签约谈判」与「公开素材清单初筛」两条不依赖代码的子流程。

---

## 一、目的与边界

### 1.1 这是什么

把 [`docs/23 §3.1`](../23-二期可编码规格说明书.md) P2-M7-01 的 FR / AC 转成"Phase 2.0 W14 当天就能开始做"的可执行手册——给算法 lead / 教研 lead / 教练 BD / 法务 / 内容运营**一份共识起点**，不用每个角色再翻 3 份 docs 拼。

**ECS v2 一句话**：用 **≥80 段、4 杆型分桶、双盲标注**的顶尖样本作为 M7 引擎 V2 评分 / 阶段分割 / 新特征算法的"参考真值"，让二期所有打分都能回答一个问题——「**这个分数为什么是这个分**，对得起谁的挥杆？」

### 1.2 这不是什么

- **不是用户上传数据**：用户在 app 内拍的视频**永远不进 ECS**（[`docs/06 §13.4`](../06-数据安全与隐私合规文档.md)），即使隐去身份也不行；想用必须**显式书面授权 + 走 DEP-02 教练签约路径**。
- **不是 mock_pipeline 的扩展**：ECS 仅服务**真实引擎**（`real_pipeline.py`），mock 不参与标定（[`docs/20 §5.3`](../20-AI引擎产品力迭代设计.md)）。
- **不是 drill 教学视频**：drill 视频是面向 C 端用户的「教练示范」（DEP-03, 见 [`drill-demo-video-revamp.md`](drill-demo-video-revamp.md)）；ECS 是面向算法内部的「评分基线」，**两份资产生产链路不交叉**。
- **不是单次拍摄就完**：v2.0.0 首版 ≥80 段, 二期持续扩容到 v2.x.x（每个 Phase 收尾时增量 review）。

### 1.3 为什么 W14 就要启动

- DEP-01 验收口径是「评审日起 **4 周内** 完成 30+ 段第一批」（[`docs/22 §四`](../22-二期开发迭代计划.md)）, 4 周里**至少 1 周是签约谈判**, 教练签约不是当天能拍板的事；
- W17 起 M7 §4.4 机位标尺 / §4.5 球杆标尺 / §4.4.4 阶段算法 V2 / §4.5.2 新特征 4 个任务**都需要 ECS v2 ≥10 段当输入**才能开工；不提前启动 = 卡 Phase 2.1 第 1 周；
- 教练签约 / 法务版权 review / 公开素材初筛三件事**没有前置代码依赖**, 完全可以与 docs/22 / docs/23 评审**并行**进行。

---

## 二、采集目标与分桶

### 2.1 总量与分桶

| 杆型 (`club_type`) | 第一批 (W17 截止) | v2.0.0 (二期收口) | 备注 |
|---|---|---|---|
| Driver | ≥8 | ≥20 | 必含 ≥2 位中国大区球手, ≥1 位左手球手（≥10° spine tilt 多样性） |
| Iron (mid: 6i/7i) | ≥8 | ≥20 | 优先 7 号铁, 6/8 号兜底 |
| Wedge (PW/SW/LW) | ≥8 | ≥20 | 不含切击专项, 切击走 P2-M7-12 单独采集 |
| Putter | ≥6 | ≥20 | 优先 face-on 机位, putter dtl 不要求 |
| **合计** | **≥30** | **≥80** | DEP-01 第一批门槛 vs ECS v2.0.0 门槛 |

### 2.2 机位与画质

| 维度 | 硬约束 | 软约束（尽量满足） |
|---|---|---|
| 机位 (`camera_angle`) | 至少一个机位 | Driver / Iron / Wedge 优先 face_on + dtl 双机位；Putter 仅 face_on |
| 帧率 (`fps`) | ≥120 fps | ≥240 fps 标 high-speed, 用于阶段边界精标 |
| 画面 | 全身入框, 球出现 | 4K 优先, 1080p 兜底 |
| 时长 | 单次挥杆完整（含 setup → finish） | 5-15s 为佳；避免多次连挥（多次挥杆走 P2-M7-13 单独 mode）|
| 光照 | 主体清晰, 阴影不遮膝 | 室内棚拍 / 室外晴天 / 室外阴天均可, 夜间 / 强逆光不收 |

### 2.3 多样性约束（避免训练偏差）

- **性别**：男 ≥70% / 女 ≥20% / 不限 ≤10%
- **利手**：右手 ≥80% / 左手 ≥10%
- **身形**：身高分布跨 165-195cm 至少 3 档；上肢 / 躯干比例不刻意筛
- **地区**：中国大区 ≥30% / PGA Tour ≥30% / EU Tour / 韩国 / 日本 ≥10% 合计
- **年龄段**：≥3 档（25 以下 / 25-40 / 40 以上）

---

## 三、样本来源清单（白名单 + 黑名单）

### 3.1 白名单：允许进 ECS 的来源

| 类别 | 具体来源 | 准入条件 | 占比上限 |
|---|---|---|---|
| **A. 公开授权素材** | PGA Tour 官方频道 / European Tour 官方 / LPGA / KPGA / JLPGA 官方频道；Bilibili 经认证的官方账号（如「高尔夫频道」「GolfTV 中国」）；球手个人官方 SNS 中**明示允许引用**的发布 | 必须有 `source_credit`（账号 + 视频标题 + 发布日期）+ `source_url`；纯"reaction / 二次剪辑"账号一律不收 | ≤50% |
| **B. 合作教练自录** | DEP-02 签约的 ≥5 位教练在我们提供的标准化拍摄指引下自录 / 摄棚 | 必须有签字版授权书（"算法研发与内测"范围）；教练身份可在 manifest 中以 `coach_alias` 隐名 | ≥40% |
| **C. 合作球手书面授权镜头** | 通过 BD 邀请的职业 / 高水平球手, 一次性授权 5-10 段 | 同 B；签约范围必须显式覆盖"ECS 标定集 + 内部话术培训, 不对外公开播放" | ≤20% |
| **D. 学术开源数据集** | 公开 paper 配套数据集（如 GolfDB / Sportlogiq 公开 split, 仅在 license 兼容时） | 必须 attach paper 引用 + license 文本到 manifest | ≤10% |

### 3.2 黑名单：**严禁**进 ECS

- ❌ **App 内用户上传 UGC**——即使该用户在 onboarding 勾过"用于 AI 改进"按钮也不行（[`docs/06 §13.4`](../06-数据安全与隐私合规文档.md)），ECS 是**对外公开打分基线**, 隐私边界更严
- ❌ **Mixkit / Pexels / Pond5 等 stock 素材**——这是 drill 视频翻车的根因（详 [`drill-demo-video-revamp.md`](drill-demo-video-revamp.md)）；这类素材"动作正确性无法验证, 仅占视觉版面"
- ❌ **微信群 / Telegram / 论坛抓的"网传"**——版权来源不可追溯, 一旦被原作者投诉无撤档能力
- ❌ **AI 生成 / 动捕重建 / 卡通示意**——ECS 是真人挥杆的"真值", 合成数据不属于该任务
- ❌ **付费购买的"职业球手数据库"**——除非买方拥有"算法训练 + 商业评分"明示授权（绝大多数体育数据公司**不卖**这条）

### 3.3 投诉与撤档

- 任何样本被原作者 / 平台 / 球手 / 教练投诉：**24h 内**从 manifest 中 `license_status` 改为 `revoked`, 视频文件从 MinIO 私桶下线（保留备份在隔离 bucket 用于追责）
- 撤档同步：`ecs_metadata.json` 提交一个 commit `chore(ecs): revoke <sample_id> per <投诉方>`，触发 ECS 回归脚本重跑（去掉该样本后基线分数是否漂移）
- 单 Phase 内撤档样本数 ≥3 → 触发 RISK-A1（见 §八）, 算法 lead 拉会 review 采集 SOP

---

## 四、Manifest schema (`ecs_metadata.jsonl`)

### 4.1 单条 JSONL 模板

```jsonl
{
  "sample_id": "ecs_v2_dr_pga_001",
  "club_type": "driver",
  "club_subtype": null,
  "camera_angle": "face_on",
  "fps": 240,
  "resolution": "3840x2160",
  "device": "iPhone 15 Pro Max + Gimbal",
  "duration_sec": 7.2,
  "captured_at": "2024-08-12",
  "captured_location": "Augusta Range",
  "player_meta": {
    "alias": "PGA_M_001",
    "gender": "M",
    "handedness": "R",
    "height_cm_range": "180-185",
    "region": "PGA_TOUR",
    "is_pro": true,
    "real_name_hash": "sha256:xxxxxx"
  },
  "license_status": "public_clip",
  "source_credit": "PGA Tour Official Channel - Tee Time clip 2024-08",
  "source_url": "https://www.youtube.com/watch?v=...",
  "license_doc_path": null,
  "phase_boundaries_gt": {
    "setup_frame": 12,
    "address_frame": 28,
    "takeaway_frame": 45,
    "top_frame": 78,
    "transition_frame": 84,
    "impact_frame": 92,
    "follow_through_frame": 130,
    "finish_frame": 175
  },
  "features_gt": {
    "tempo_ratio_backswing_to_downswing": 3.2,
    "weight_shift_top_to_impact_pct": 88,
    "kinematic_sequence_pelvis_to_shoulder_lag_ms": 90,
    "kinematic_sequence_shoulder_to_arm_lag_ms": 55,
    "head_stability_max_offset_cm": 4.2,
    "spine_angle_at_address_deg": 38,
    "spine_angle_change_setup_to_top_deg": 4.1
  },
  "annotators": [
    {"alias": "coach_zhang", "annotated_at": "2026-06-10", "role": "primary"},
    {"alias": "coach_li", "annotated_at": "2026-06-11", "role": "blind"}
  ],
  "arbitration": {
    "status": "consistent",
    "arbitrator_alias": null,
    "max_boundary_delta_frames": 2,
    "max_feature_delta_pct": 3.4
  },
  "ecs_version": "v2.0.0",
  "ingested_at": "2026-06-15T03:24:11Z",
  "notes": null
}
```

### 4.2 字段含义速查

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `sample_id` | string | ✅ | 命名规范 `ecs_v2_<club_short>_<source_short>_<3 位序号>`；`dr/ir/wd/pt` 四杆型缩写 |
| `club_type` | enum | ✅ | `driver` / `iron` / `wedge` / `putter` |
| `club_subtype` | string \| null | ❌ | 如 `7i` / `pw` / `54_deg_wedge`；不强求 |
| `camera_angle` | enum | ✅ | `face_on` / `dtl`（down_the_line）|
| `fps` | int | ✅ | 拍摄帧率, ≥120 |
| `player_meta.real_name_hash` | string | ✅ | 真实姓名 sha256, **不入库明文**；用于"同一球手是否被多次采样"去重 |
| `player_meta.alias` | string | ✅ | 公开素材沿用频道命名（如 `PGA_M_001`）；合作教练 / 球手匿名编号（`coach_zhang_anon` / `signed_player_007`）|
| `license_status` | enum | ✅ | `public_clip` / `coach_authorized` / `player_authorized` / `academic_open` / `revoked` |
| `license_doc_path` | string \| null | B/C/D 必填 | 签字版授权书在私有 git-LFS 的相对路径（不可走 git 主仓） |
| `phase_boundaries_gt` | object | ✅ | 8 个关键帧号（与 P2-M7-07 阶段分割算法 V2 对齐）|
| `features_gt` | object | ✅ | 5 个新特征 + 2 个传统特征的"人工真值"（与 P2-M7-08 对齐）|
| `annotators` | array | ✅ | 至少 2 位独立标注 |
| `arbitration.status` | enum | ✅ | `consistent` / `arbitrated` / `pending` / `rejected` |
| `ecs_version` | string | ✅ | `v2.0.0` 起；每次 minor 升级新增 ≥5 段 / patch 升级修正既有标注 |

### 4.3 manifest 存储

| 资产 | 存储 | 备份 |
|---|---|---|
| `ecs_metadata.jsonl`（manifest 单文件） | git 主仓 `ai_engine/calibration/ecs_v2/manifest.jsonl` | 每次 PR 走双 reviewer + 算法 lead 必签 |
| 视频文件（mp4） | MinIO 私有 bucket `ecs-v2-private/` | 双地域备份；外网不可访问；后端 staging / prod 都不挂载该 bucket |
| 授权书扫描件（pdf） | git-LFS 私有镜像仓 `ecs-v2-license-private`（**不进主仓**）| 法务团队季度 audit |
| 标注一致性报告 | git 主仓 `ai_engine/calibration/ecs_v2/reports/<date>_consistency.md` | review 会议存档 |

---

## 五、双盲标注流程

### 5.1 单段样本的标注生命周期

```
[原始视频] → ingest → [pending] → [annotator_1 标] → [annotator_2 盲标]
                                                          ↓
                                                  [一致性自动 diff]
                                            ┌────────────┴────────────┐
                                            ↓                          ↓
                          阶段边界 ±3 帧 内              阶段边界 ±3 帧 外
                          特征值 ±5% 内                  或特征值 ±5% 外
                                            ↓                          ↓
                                    [consistent]               [仲裁]
                                            ↓                          ↓
                                    入 manifest          arbitrator 第 3 教练判
                                                                       ↓
                                                              ┌────────┴────────┐
                                                              ↓                  ↓
                                                       [arbitrated 入]   [rejected 移出]
```

### 5.2 一致性阈值

| 维度 | 阈值 | 超阈值动作 |
|---|---|---|
| 阶段边界帧号 | 任一关键帧 \|Δframe\| > 3 | 触发仲裁 |
| `tempo_ratio` | \|Δ\|/mean > 5% | 触发仲裁 |
| `weight_shift_top_to_impact_pct` | \|Δ\|abs > 5pp | 触发仲裁 |
| `head_stability_max_offset_cm` | \|Δ\|/mean > 5% 或 \|Δ\|abs > 1.5cm | 触发仲裁 |
| 其他 features | \|Δ\|/mean > 8% | 触发仲裁 |

### 5.3 标注吞吐目标

- **教练个人**：≥10 段 / 周（含 face_on + dtl 计 2 段）
- **团队整体**：W15 起每周交付 ≥10 段 consistent 入 manifest, W17 累计 ≥30 段
- **仲裁占比**：< 25% 为健康；> 35% 触发 RISK-A2 review 标注 SOP

### 5.4 标注工具

- **W14-W15 用 csv + 视频播放器手工标**（不阻塞采集启动；csv 模板见 §附录 B）
- **W16 起评估**：直接复用一期 `ai_engine/scripts/replay/` 骨架, 加一个 web-based timeline UI（不强求, 算法 lead 决策）；或采购成熟方案如 `cvat.ai` self-hosted
- **AC**：不论工具如何, 最终落到 `ecs_metadata.jsonl` 结构 §4.1 一致

---

## 六、数据安全与法务

### 6.1 数据安全清单

| 项 | 要求 | 责任 |
|---|---|---|
| EXIF 脱敏 | 上传前必须 strip GPS / device-serial / owner_id 等 EXIF 元数据；保留 fps / 分辨率 / 时长 | 算法 + 工程 |
| 面部脱敏 | 公开素材 (A 类) 不动脸；合作 (B/C 类) 默认不动脸但保留教练 / 球手"撤档申请"通道 | 算法 |
| 上传通道 | 仅允许走内网 / VPN 上传 MinIO `ecs-v2-private/`；外网严禁 | 工程 + 运维 |
| 加密 | bucket SSE-S3 + 跨地域备份；访问凭据按 IAM 角色 `ecs-readonly` / `ecs-write` 分级 | 运维 |
| 主仓提交 | `ecs_metadata.jsonl` 进 git 主仓时**自动 lint** 检查所有 `license_status != revoked` 的样本都有 `source_credit`，缺失即拒 | 工程（pre-commit hook）|
| 审计 | 每季度由法务 + 算法 lead 联合 audit 一次：抽样 20% 样本检查授权书完备性 + manifest 字段一致性 | 法务 + 算法 |

### 6.2 法务清单

- **签约样板**（教练 B 类）：见 §附录 C；范围必须显式覆盖"算法研发 + 内测 + 阶段性产品话术示例"，**不**含"对外公开播放 / 商业广告 / 二次销售"
- **公开素材清单**（A 类）：每条入 manifest 前在 [Music & Effects License Checker](https://www.youtube.com/) / 官方频道 ToS 上确认"Educational use / Fair use" 适用；模糊地带请法务 case-by-case 出意见
- **撤档机制**：见 §3.3
- **未成年人**：≤18 岁球手镜头必须**家长 / 监护人**签同意书；未签的一律不收（公开素材也不行, 用 player_meta.age_range 字段过滤）
- **跨境数据**：本 ECS 服务仅部署在国内, MinIO 私桶仅国内 region；不向境外传输（[`docs/06 §13.5`](../06-数据安全与隐私合规文档.md)）

### 6.3 与 docs/06 §13 的映射

| docs/06 §13 章节 | 本启动包对应章节 |
|---|---|
| §13.1 M9 敏感字段（身体数据） | N/A, ECS 不收集 |
| §13.4 ECS 与 UGC 隔离 | §1.2 + §3.2 黑名单 |
| §13.5 跨境数据 | §6.2 末段 |
| §13.6 数据资产撤档 | §3.3 |

---

## 七、W14-W17 周计划与 DoD

> 周次相对：W14 = docs/22 评审日（一期收尾后第 1 周）

### 7.1 W14 · 启动周

| 日 | 动作 | 责任 | DoD |
|---|---|---|---|
| D1-D2 | 本启动包 v0.1 评审（产品 + 算法 + 教研 + 法务 + 内容运营 5 方 1h 会议） | PM | 评审 minutes 入档；分歧项 v0.2 修订 |
| D2-D5 | 教练签约谈判启动（≥5 位候选）；签约样板 §附录 C 法务过 | BD + 法务 | 候选清单 + 谈判时间表 |
| D2-D7 | 公开素材清单初筛（A 类）：每杆型先扒 30 段候选, 待法务过 | 内容运营 + 法务 | 候选 jsonl（无 features_gt, 只填 meta + source）|
| D3-D7 | MinIO 私桶 `ecs-v2-private/` 配 + IAM 角色 + 上传通道演练 | 运维 + 工程 | 1 段测试样本走通 ingest → manifest dry-run |

### 7.2 W15 · 第一批入库

| 日 | 动作 | 责任 | DoD |
|---|---|---|---|
| D1-D3 | 教练 ≥3 位签约落定 | BD | 授权书 PDF 入 git-LFS 私镜 |
| D1-D7 | 标注培训：≥2 位教练 + 1 位算法 review 试标 5 段, 校准阈值 | 算法 + 教研 | 5 段试标的双盲一致性报告 |
| D3-D7 | A 类公开素材 ≥10 段入 MinIO + manifest pending | 内容运营 + 工程 | manifest.jsonl 有 ≥10 段 `arbitration.status=pending` |
| D5-D7 | 第一批 ≥10 段进入双盲标注 | 教练 + 算法 | W15 末标注吞吐自检 |

### 7.3 W16 · 双盲首批 + 一致性 review

| 日 | 动作 | 责任 | DoD |
|---|---|---|---|
| D1-D5 | 第一批 10 段双盲标注完成 + 一致性 diff | 教练 + 算法 | 一致性报告 W16 D5 出 |
| D3-D7 | A + B 类累计 ≥20 段 ingest | 内容运营 + 工程 | manifest 满 20 |
| D5-D7 | 第二批 10 段双盲启动 | 教练 + 算法 | manifest 中 ≥10 段 consistent |
| D7 | 中期 review 会：分桶覆盖率 + 仲裁率 + 法务 audit | 全员 | review minutes + W17 调整项 |

### 7.4 W17 · DEP-01 第一批门槛达成

| 日 | 动作 | 责任 | DoD |
|---|---|---|---|
| D1-D5 | manifest ≥30 段 consistent + ECS v2.0.0 tag | 算法 lead | `git tag ecs_v2.0.0` + 一致性总报告 |
| D3-D7 | 用 ECS v2.0.0 在一期 V1 引擎跑回归脚本, 出基线分数表 | 算法 + AI 工程 | docs/20 §五 更新 v2 进度 + 基线 csv |
| D5-D7 | DEP-01 验收会（[`docs/22 §四`](../22-二期开发迭代计划.md)）：通过则 DEP-01 状态切「已就绪」, M7 §4.4 / §4.5 / §4.4.4 / §4.5.2 4 任务正式开工 | 算法 lead + PM | DEP-01 状态切；docs/22 §四 更新 |

---

## 八、责任人 / 风险 / 验收

### 8.1 责任人骨架

| 角色 | 人数 | 主要职责 |
|---|---|---|
| 算法 lead | 1 | 阈值制定 / 仲裁 / 回归脚本 / ECS 版本管理 |
| AI 工程 | 1 | ingest pipeline / lint hook / 一致性 diff 自动化 |
| 教研 lead | 1 | 标注 SOP / 培训 / 仲裁第 3 教练协调 |
| 教练 BD | 1 | 签约谈判 / 拍摄沟通 |
| 内容运营 | 0.5 | A 类公开素材清单 / 撤档申请处理 |
| 法务 | 0.5 | 授权书 review / audit / 跨境合规 |
| 运维 | 0.5 | MinIO 私桶 / 备份 / IAM |
| 产品 | 0.5 | 评审主持 / 与 docs/22 / docs/23 同步 |
| **合计** | **5 人月（W14-W17 4 周）** | |

### 8.2 风险登记

| ID | 风险 | 影响 | 缓解 |
|---|---|---|---|
| RISK-A1 | 单 Phase 撤档样本 ≥3 | 基线漂移 + 法务信任受损 | 算法 lead 拉会 review 采集 SOP；考虑下调 A 类占比 |
| RISK-A2 | 仲裁率 > 35% | 标注成本爆炸 + ECS 质量低 | 教研 lead 重培训；阈值临时放宽到 ±5 帧 + ±7% 1 周, 同时积累仲裁案例库 |
| RISK-A3 | DEP-02 教练签约 < 5 位 | B 类占比目标达不成 | A 类占比上限临时放到 60%；W18 起补签 |
| RISK-A4 | A 类被官方频道下架 / 法务 retract | 影响 30%+ 样本 | 季度 audit 提前；建立 mirror（仅算法用, 不外传）|
| RISK-A5 | W14 启动包评审过不了 / 大改 | 启动滞后 | 评审前 1 周邮件预审, 收集书面意见再开会, 减少现场扯皮 |

### 8.3 验收口径（对齐 [`docs/23 §3.1`](../23-二期可编码规格说明书.md) AC）

- [ ] **AC-1**：W17 末 manifest 含 ≥30 段, 4 杆型分桶覆盖率 100%（每桶 ≥6 段）；W42 末 v2.x.x manifest ≥80 段, 每桶 ≥20
- [ ] **AC-2**：W16 末双盲一致性报告产出, 阶段边界 IoU ≥ 0.9（按 manifest 中 `arbitration.max_boundary_delta_frames ≤ 3` 占比 ≥ 75% 测算）
- [ ] **AC-3**：[`docs/20 §五`](../20-AI引擎产品力迭代设计.md#五世界顶尖样本标定集elite-calibration-set-ecs) 章节由本启动包负责升级到 v2 进度
- [ ] **AC-4**：W17 末用 ECS v2.0.0 对一期 V1 引擎跑一次回归, 产出基线分数表（csv 入 git 主仓 `ai_engine/calibration/ecs_v2/baselines/v1_engine_baseline.csv`）
- [ ] **AC-5**：W15 末教练签约清单 ≥5 位入档（含 1 位 PGA 持证 + 1 位中国大区）

---

## 附录 A：公开素材候选清单（W14 D2-D7 内容运营初筛起点）

> 仅为「初筛起点」，每条入 manifest 前**必须**走 §6.2 法务清单逐条 review。

| 优先级 | 来源类型 | 频道 / 平台 | 备注 |
|---|---|---|---|
| P0 | YouTube 官方 | PGA TOUR / DP World Tour / LPGA / LIV Golf | Tee Time / Highlight 类剪辑 Driver / Iron 多 |
| P0 | YouTube 官方 | Me and My Golf / Rick Shiels / Golf Sidekick | 中-长教学频道, 已有大量公开示范, 但 fair-use 边界要法务 case-by-case |
| P1 | Bilibili 认证 | 「高尔夫频道」「GolfTV 中国」「Golfit 高博文」 | 中国大区主力来源, fps 普遍 60-120, 选高帧率剪辑 |
| P1 | YouTube 球手个人 | Tiger Woods / Rory McIlroy / Scottie Scheffler 官方 channel | 通常需挑战 fair-use, 但球手 SNS 短片 30s 内的 swing snippet 多有 educational tag |
| P2 | 学术开源 | GolfDB (Mcnally et al.) / Sports Pose Database | license 兼容性要 paper 配套 README 确认 |
| P2 | KPGA / JLPGA | 韩国 / 日本职业巡回赛官方 | 韩国 / 日本女子球手姿势特征对中国大区参考价值高 |

## 附录 B：W14-W15 试标 csv 模板（评估期临时用, W16 切 manifest.jsonl）

```csv
sample_id,club_type,camera_angle,fps,source_url,annotator_alias,setup_frame,top_frame,impact_frame,follow_frame,tempo_ratio,weight_shift_pct,head_offset_cm,notes
ecs_v2_dr_pga_001,driver,face_on,240,https://...,coach_zhang,12,78,92,130,3.2,88,4.2,
ecs_v2_dr_pga_001,driver,face_on,240,https://...,coach_li,11,79,91,129,3.3,87,4.5,boundary tight
```

## 附录 C：教练签约样板话术摘要（法务出具最终版前的占位）

```
本协议授权方（教练）将其名下挥杆视频镜头（包括但不限于
___ 段, 总时长约 ___ 分钟, 详见附件清单）授予被授权方
（领翼golf 运营主体, 全称: ___）用于:
  (a) AI 算法的训练 / 验证 / 回归测试；
  (b) 内部技术培训 / 算法 review 材料；
  (c) 阶段性产品话术示例 (示例需教练事前书面确认);

不包含:
  (i)  对外公开播放 / 商业广告 / 二次销售;
  (ii) 在 C 端产品内作为「教练示范视频」展示 (该用途走
       drill 教学视频独立签约,详 DEP-03);
  (iii) 跨境数据传输或转授权给第三方。

授权方有权于任意时点书面要求撤档,被授权方应在 24 小时
内从 ECS manifest 与对象存储下线,保留隔离备份仅用于
追溯, 不再用于算法训练。
```

> ⚠️ 上文仅为业务诉求摘要, **不构成法律文书**；正式合同必须由 DEP-05 同一家律师事务所出具。

---

## 文档变更记录

| 日期 | 版本 | 说明 |
|---|---|---|
| 2026-05-25 | v0.1 | 启动输入稿：8 章主体 + 3 附录；W14 评审通过后由 PM 维护 v0.2 起。**不动 docs/22 / docs/23 / docs/20 任何字段**, 待 docs/22 v0.1（PR #19）+ docs/23 v0.1（PR #20）合并后，本启动包再起 v0.2 加回链到 docs/22 §四 DEP-01 / docs/23 §3.1 文档同步行 / docs/20 §五。 |
