# APP-SP-1 · 帧率对照 Spike 操作手册

> **状态**：进行中 · 配套 [`app-m0-m1-kickoff-checklist.md`](./app-m0-m1-kickoff-checklist.md) §3  
> **目标**：用同一挥杆场景，对比三组素材的分辨率 / fps / 体积 / 是否可分析，为 **APP-SP-2 默认拍摄档** 提供数据。  
> **不做**：弹道描线成片（Q-D2）。

---

## 1. 三组怎么拍

| 组别 | 怎么拿到视频 | 工程入口 |
|------|--------------|----------|
| **微信小程序** | 体验版小程序 → 首页「拍挥杆」→ **开始拍摄**（`chooseMedia`，通常 ~30fps） | weapp `adapters/media` |
| **系统慢动作导入** | iOS「相机 → 慢动作」拍 5～10s → App **从相册选择** 导入 | RN album · `chooseVideo({ source:'album' })` |
| **App 原生高帧率** | App 内 **开始拍摄**（`launchCamera` + `videoQuality:high`，**best-effort**；多数机型仍接近 30fps） | RN camera · preset `high_quality` |

说明：当前 `react-native-image-picker` **无法强制 120/240fps**。若「App 内拍摄」实测与微信同档，以「系统慢动作导入」作为高帧率臂的主证据；原生高帧模块另排期。

建议：同一球员、同一角度（Face-On 或 DTL）、尽量同光照，每组至少 2 条（一条 5s、一条 ~8s）。

---

## 2. 探针（填表）

本机安装 ffprobe 后：

```bash
# 从手机隔空投送 / 线缆导出到 Mac 后
bash scripts/probe-video-meta.sh ~/Desktop/weapp.mp4 ~/Desktop/slowmo.mov ~/Desktop/app-cam.mov
```

把输出里的 **分辨率 / avg_frame / 体积** 填入 kickoff §3 结果表。

App 选片当下也可在 Metro 日志搜 `SP1-pick`：capture 页会 `console.info` 一行摘要（`formatVideoPickSummary`）。

---

## 3. 「可分析 / 硬拦」怎么记

对每条样本走完：**params → 上传 → waiting → 报告**（或停在硬拦 toast）。

| 结果 | 记法 |
|------|------|
| 出报告 | `可分析` + 总分 / trust（可选） |
| 时长 / 体积 / 扩展名前端拦 | `硬拦·客户端：…` |
| 引擎质量门 / preprocess 失败 | `硬拦·引擎：…`（抄 waiting/toast） |

---

## 4. 验收

- [ ] 结果表三行均有分辨率、实测 fps、体积、可分析结论  
- [ ] 备注写清机型（如 iPhone 15 Pro）与系统版本  
- [ ] 产品根据表启动 **APP-SP-2** 默认档签字（本 runbook 不代签）

---

## 5. 修订

| 版本 | 日期 | 说明 |
|------|------|------|
| v0.1 | 2026-07-20 | 初版：三臂定义 + `probe-video-meta.sh` + 与 M1-1 album/camera 对齐 |
