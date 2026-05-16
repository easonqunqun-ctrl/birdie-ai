# W8 真机内测 · 证据归档目录

> 本目录存放 W8-T6 团队真机走查过程中产出的**素材证据**：真机截图 / 录屏 GIF / 后端响应 JSON 快照 / 关键 SQL 结果。
>
> 与 [W8-internal-walkthrough.md](../W8-internal-walkthrough.md) 的编号**一一对应**——walkthrough 里每一步"证据位"都指向本目录下的文件名。

---

## 目录结构约定

```
W8-evidence/
├── README.md                   # 本文件
├── source-media/               # 走查用的原始素材（不提交二进制到 git，.gitignore）
│   ├── .gitkeep
│   ├── swing_normal.mp4        # 正常挥杆 3-10s
│   ├── swing_too_short.mp4     # 1s 过短素材
│   └── violation_sample.jpg    # 文件名含 "violation" → 触发 mediaCheck mock 拒绝
├── screenshots/                # 真机截图（png，带设备/系统/时间水印更好）
│   ├── .gitkeep
│   ├── step01-consent.png      # 编号与 walkthrough §5 一一对应
│   ├── step02-onboarding.png
│   ├── step03-capture.png
│   ├── step04-params.png
│   ├── step05-waiting.png
│   ├── step06-report.png
│   ├── step07-coach.png
│   ├── step08-share-card.png
│   ├── step09-public-report.png
│   └── step10-membership.png
├── recordings/                 # 短录屏 → 转 GIF（≤ 5MB/段）
│   ├── .gitkeep
│   ├── full-loop.gif           # 完整 10 步闭环（建议 ≤ 60s，加速 1.5-2x）
│   └── share-card.gif          # 分享卡片生成 + 撤回
├── api-samples/                # 关键 API 真机请求响应 JSON（从 F12/抓包粘贴）
│   ├── .gitkeep
│   ├── wechat-login.json
│   ├── create-analysis.json
│   ├── report.json
│   └── track-events.json
└── sql-snapshots/              # 关键 SQL 结果（\o 导出 txt 或 md 粘贴）
    ├── .gitkeep
    ├── users-latest.txt        # 本轮测试产生的 users 明细
    ├── events-funnel.txt       # W8-metrics-cheatsheet.md §2 转化漏斗
    └── orders-mockpay.txt      # mock_pay.sh 后 users + analysis_quotas 验证
```

---

## 命名规范

1. **顺序** 用 `stepNN-` 前缀（`step01` ~ `step10`），与 walkthrough §5 的 10 步脚本严格对齐，便于交叉查阅
2. **设备/环境后缀** 可选：`step06-report-iphone15pro-ios18.png`、`step06-report-huaweimate60-hmos.png`（跨设备都有就加，单设备不加）
3. **时间戳** 文件内部截图自带即可，不用放文件名
4. **失败用例** 用 `bugNN-<短描述>.png`（例 `bug01-quota-still-3.png`），在 walkthrough §6 bug 登记表引用

---

## 什么要进 git，什么不进

| 类型 | 入库 | 理由 |
|---|---|---|
| `README.md`（本文件） | ✅ | 文档 |
| `.gitkeep` 占位 | ✅ | 保持目录结构 |
| `screenshots/*.png` ≤ 500KB/张 | ✅ | 评审 + 回溯凭证；超过就压缩 |
| `recordings/*.gif` ≤ 5MB/段 | ✅ | 同上；超过就剪短或降帧 |
| `api-samples/*.json` | ✅ | 字节小，且复现 bug 时必要 |
| `sql-snapshots/*.txt` | ✅ | 字节小 |
| `source-media/*.mp4`、`.mov` 等原始视频 | ❌ | 二进制大，隐私风险；只进 `.gitkeep`，实际素材放在本地或 MinIO |

建议在 repo 根 `.gitignore` 加一段：

```gitignore
docs/release-notes/W8-evidence/source-media/*
!docs/release-notes/W8-evidence/source-media/.gitkeep
```

---

## 最小可交付（Definition of Done for T6）

walkthrough 跑完一轮，本目录至少产出：

- [ ] `screenshots/` ≥ 10 张（10 步每步一张）
- [ ] `recordings/full-loop.gif` ≥ 1 段（端到端闭环）
- [ ] `sql-snapshots/events-funnel.txt`（W8-metrics-cheatsheet.md §2 真机数据）
- [ ] `sql-snapshots/users-latest.txt`（至少 2 个真机账号）
- [ ] `../W8-internal-walkthrough.md` §6 bug 列表填好，P0=0 或"已修+二次验证截图入库"
