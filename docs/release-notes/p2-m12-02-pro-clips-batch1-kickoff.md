# P2-M12-02 · 第一批 10-20 位球手公开镜头入库 + ECS v2 关联 · 启动包（W22 起跑）

> 版本：v0.1（2026-05-25）
> 状态：启动输入稿
> 适用范围：二期 Phase 2.1 期间，落地球手镜头首批入库 + 与 ECS v2 关联
> 上游真源（待 PR #20 合并后生效）：[`docs/23 §8.2 · P2-M12-02`](../23-二期可编码规格说明书.md#82-p2-m12-02--第一批-10-20-位球手公开镜头入库--ecs-v2-关联)
> 前置 kickoff：[`p2-m12-01-pro-library-schema-kickoff.md`](./p2-m12-01-pro-library-schema-kickoff.md)（**硬依赖**：6 表 schema 就绪） + [`p2-m7-01-ecs-v2-kickoff.md`](./p2-m7-01-ecs-v2-kickoff.md)（共享镜头采集 SOP）
> 合规：[`docs/06 §13.3`](../06-数据安全与隐私合规文档.md)（版权合规）

---

## 一、文档目的与边界

### 1.1 目的

为 **P2-M12-02 第一批球手入库**落地一份「**W22 即可起跑（M12-01 W19 + M7-01 W18 已完成）、W28 ≥80 段 clip 入库**」的内容 + 算法 + 法务 SOP：

- 入库 ≥10 位球手（首批 10 + 后续扩 20）；以 PGA/LPGA/中国巡回赛公开镜头为主
- 至少 1 位中国球手 `partnership` 授权样板
- 每段 clip 走 M7 V2 预处理生成 `normalized_video_url` + `skeleton_video_url` + `features_snapshot`
- 撤稿 24h SLA + 白名单 / 黑名单 SOP

### 1.2 边界（**不**做项）

| 不做 | 原因 |
| --- | --- |
| 不修改 docs/22 / docs/23 / docs/03 / docs/06 字段 | 避免与 #18/#19/#20 race |
| 不动 6 表 schema | M12-01 已就位 |
| 不实现资源库 tab UI | M12-03 负责 |
| 不实现匹配算法 | M12-04 负责 |
| 不入库非公开来源（盗摄、群文件等） | 合规红线 |
| 不引入 LPGA 选手"形象权"敏感样本 | 法务评估后再放 |

---

## 二、现状盘点

### 2.1 上下游已就位组件

| 组件 | 状态 | 用途 |
| --- | --- | --- |
| M12-01 6 表 schema | W19 完成 | 数据落地 |
| M7-01 ECS v2 manifest | W18 完成 | 共享拍摄 / 法务标准 |
| M7 V2 引擎（W22+ 灰度） | W22 起 5% | 给 pro_swing_clips 跑预处理 |
| 一期 ai_engine pipeline | 已上线 | 评分 / skeleton 生成 |

### 2.2 已知缺口（vs docs/23 §8.2 FR）

| FR | 现状 | 缺口 |
| --- | --- | --- |
| FR-1 ≥10 位球手 | ❌ | 内容运营选材 |
| FR-2 公开镜头来源 | ❌ | YouTube / 官方频道收集 |
| FR-3 1 位中国球手 partnership | ❌ | 法务谈授权 |
| FR-4 每球手 3-8 段（≥2 机位 × ≥2 杆型） | ❌ | 内容编排 |
| FR-5 source_credit 必填 | M12-01 NOT NULL 约束 | 录入工具校验 |
| FR-6 ECS v2 关联 + features_snapshot | ❌ | 跑 V2 预处理 |
| FR-7 normalized_video_url + skeleton_video_url | ❌ | M7 V2 pipeline 产出 |
| FR-8 撤稿白 / 黑名单 SOP | ❌ | 运营文档 |

---

## 三、模块设计

### 3.1 工作量分解

| 任务 | 责任方 | 工作量 |
| --- | --- | --- |
| 球手筛选 + 镜头收集（PGA / LPGA / 中国巡回） | 内容运营 | 1.5 PW |
| 法务复核 + 中国球手 partnership 谈授权 | 法务 | 1 PW |
| Admin 录入工具（最小 MVP） | 工程 | 1 PW |
| M7 V2 预处理跑 ≥80 段 | 算法 | 0.5 PW |
| 撤稿白 / 黑名单 SOP 文档化 | 运营 + 法务 | 0.5 PW |
| 数据质量复核 | 教研 / 算法 | 0.5 PW |
| 总缓冲 | — | 1 PW |

**合计：~6 PW**（与 docs/23 §8.2 持平）

### 3.2 球手筛选清单（W22 评审冻结）

| 类别 | 数量目标 | 来源 |
| --- | --- | --- |
| PGA 顶尖（Rory / Scottie / Jon Rahm 等） | 4 位 | YouTube PGA TOUR / 大师赛官方 |
| LPGA（Lydia Ko / Nelly Korda 等） | 2 位 | YouTube LPGA 频道 |
| 中国巡回赛 / 海外华人（吴阿顺 / 林希妤 / 张华创等） | 2 位 + 1 位 partnership | 中高协 / 个人公众号 |
| 经典 / 退役（Tiger / Faldo 教学片） | 2 位 | YouTube 教学频道 |

合计首批 10 位；后续扩到 20 位。

### 3.3 单球手镜头编排

- ≥3 段 / 球手；≤8 段 / 球手
- 至少 2 机位（face_on + dtl）
- 至少 2 杆型（建议 driver + 7-iron + wedge 三件套）
- 每段 6-12 秒（含起势 + 击球 + 收杆完整）

### 3.4 Admin 录入工具 MVP

- 路由：`/admin/pro-clips`（admin role）
- 表单：球手选择 / 上传视频 / source_credit / source_url / club_type / camera_angle / license_status
- 提交后异步触发 M7 V2 预处理 → 写入 `features_snapshot` + skeleton_video_url
- 处理失败可重试

### 3.5 与 ECS v2 manifest 关联

- 同一段视频既可入 `pro_swing_clips`，也可（必要时）入 ECS v2 标定集
- 关联键：相同的原始 URL（`source_url` + `captured_year`）
- M7-01 manifest 行可标记 `linked_pro_clip_id`（向后兼容字段）

### 3.6 撤稿 SOP（FR-8）

1. **触发**：收到投诉 / 法务通知 / 运营巡检发现
2. **24h 内**：admin 设 `is_active=false` + `is_published=false`（不删除数据）
3. **7 天内**：法务复核 → 永久下架 或 恢复
4. **永久下架**：`DELETE FROM pro_swing_clips WHERE id=...`（M12-01 CASCADE 链路自动清理 annotations / favorites / match_history）

**黑名单**：被下架球手 / 来源进入运营 `pro_blacklist` 表（W23 评估是否单独建表）

---

## 四、字段 / 配置草案 v0.1

### 4.1 录入工具 API

```
POST /v1/admin/pro-clips
Body: { pro_player_id, video_file (multipart), source_credit, source_url, license_status, ... }
Response: { id, status: 'processing', processing_job_id }
```

### 4.2 配置项

```python
PHASE2_PROS_ENABLED: bool = False  # M12-03 上线时切 true
```

---

## 五、验证数据

### 5.1 数据完整性

- ≥10 位球手 + ≥80 段 clip
- source_credit 完整率 100%
- features_snapshot 数据完整率 100%
- ≥1 位中国球手 partnership 授权样板

### 5.2 撤稿演练（AC-4）

- staging：admin 一键 is_active=false → 24h 内客户端列表消失
- 永久删除路径 → CASCADE 验证

---

## 六、W22-W28 周计划

| 周 | 任务 | DoD |
| --- | --- | --- |
| **W22** | 本文件评审；球手筛选清单冻结；法务确定 partnership 候选 | ☑ 10 位首批清单；☑ 法务签字 |
| **W23** | Admin 录入工具开发 | ☑ MVP 上线 |
| **W24-W25** | 首批 50% 镜头入库（含 partnership 中国球手 1 位） | ☑ ≥40 段 clip |
| **W26-W27** | 剩余 50% 入库 + M7 V2 预处理 | ☑ ≥80 段 clip + features_snapshot 全 |
| **W28** | 撤稿演练 + 数据质量复核 | ☑ AC-1/2/3/4 全勾 |

---

## 七、责任 / 风险 / 验收

### 7.1 责任

| 角色 | 责任 |
| --- | --- |
| 内容运营 Lead | 总 owner；球手筛选 + 镜头收集 + 录入 |
| 法务 | partnership 授权 + 撤稿审核 |
| 算法 | M7 V2 预处理 + features_snapshot 校验 |
| 工程 | Admin 录入工具 + CASCADE 链路验证 |

### 7.2 风险

| ID | 风险 | 兜底 |
| --- | --- | --- |
| R-01 | YouTube 视频被原 uploader 投诉 | 24h 下架 SOP；优先采用 PGA TOUR 官方频道（投诉概率低） |
| R-02 | 中国球手 partnership 谈不下 | 退而求其次：找有公开教学短视频的退役教练（无 partnership 也能 public_clip 入库） |
| R-03 | M7 V2 灰度未覆盖 admin 录入流量 | Admin 路径强制走 V2 容器（不参与灰度分桶） |
| R-04 | LPGA 选手形象权敏感 | 法务评估；首批选 LPGA 公开教学内容（非赛场近景） |
| R-05 | 80 段视频版权审核工作量大 | 优先用同一频道集中来源（PGA TOUR 一家 vs 多家），降低审核家次 |

### 7.3 AC 兜底（复述 docs/23 §8.2）

- [ ] **AC-1**：≥10 位球手 / ≥80 段 clip
- [ ] **AC-2**：source_credit 完整率 100%
- [ ] **AC-3**：≥1 位中国球手 partnership
- [ ] **AC-4**：撤稿演练通过（24h 内）

---

## 八、附录

### 8.1 与相邻 PLAN-ID 分工

| 任务 | 关系 |
| --- | --- |
| P2-M12-01 数据模型 | 6 表 schema 就位 |
| P2-M7-01 ECS v2 | 共享拍摄 / 法务标准；可关联 manifest |
| P2-M7-14 灰度 | Admin 录入流量强制走 V2 容器 |
| P2-M12-03 资源库 UI | 消费本任务入库数据 |
| P2-M12-04 匹配算法 | 消费 features_snapshot |
| P2-M11-02 课程内容 | 引用 pro_clip_ids（lesson 可引球手镜头） |

### 8.2 source_credit 模板（W22 评审冻结）

```
"Source: PGA TOUR 官方频道（YouTube：https://youtu.be/{video_id}） · 2024 Masters R3"
"Source: 球手林希妤个人授权（2025-MM-DD authorized）"
"Source: 中高协合作 · 2025 杯赛 R2（partnership）"
```

---

## 九、变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-05-25 | 初版；10 位首批清单 + 撤稿 24h SOP + W22-W28 周计划 |
