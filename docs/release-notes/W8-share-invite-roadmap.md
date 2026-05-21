# W8 分享与邀请 · Roadmap（海报 / 小程序码）

> MVP [`docs/01` §7](../01-MVP功能需求规格说明书.md) 延后项；当前主线为原生 `openType='share'` + 复制邀请码。**本文件仅列开发队列，不写实现臆测**。

## 队列

| 阶段 | 项 | 说明 |
|------|-----|------|
| P1 ✅ | `wxacode.getUnlimited` / 服务端生成小程序码 | **已交付**：`POST /v1/analyses/{id}/share-card` → 服务端调用 wxacode、落 COS/MinIO；客户端在 report 页 & 海报页拉取；TTL 由后端 share 服务统一管理 |
| P1 ✅ | 750×1334 分享海报 Canvas | **已交付**：[`pages/analysis/poster.tsx`](../../client/src/pages/analysis/poster.tsx) 离屏 `Canvas type='2d'` 合成；版式 + 调色板对齐 [`app.scss`](../../client/src/app.scss) 与品牌四色；纯绘制函数抽离至 [`utils/posterCanvas.ts`](../../client/src/utils/posterCanvas.ts) / [`utils/posterLayout.ts`](../../client/src/utils/posterLayout.ts)，由 jest 单测覆盖（49 case） |
| P1 ✅ | 保存到相册 + 转发给好友 | **已交付**：`Taro.authorize({ scope: 'scope.writePhotosAlbum' })` 二段授权 + `openSetting` 兜底；`saveImageToPhotosAlbum`；转发用 `Button openType='share'` + `useShareAppMessage` 把 Canvas 临时 PNG 作为 `imageUrl` |
| P2 | **朋友圈封面**（Skyline / `useShareTimeline`） | 当前 Taro 项目 share-timeline 未配；待评估 Skyline 落地与 `useShareTimeline` 支持，再加自定义图 |
| P2 | 并排历史报告对比 | 见 [`Q-B2`](../19-产品开发迭代计划-当前队列.md) §三；尚未开发 |
| — | OSS/CDN URL | COS 静态资源域名与 CDN 缓存策略（见 **`W9-code-vs-plan-status`**）|

契约：`POST /v1/analyses/{id}/share-card` 已落地，见 [**`docs/02`**](../02-API接口设计文档.md)。

## 客户端实现要点（Q-C1 落地纪要）

- **路由**：`pages/analysis/poster?id=<analysis_id>`，从报告页底部「🖼 生成分享海报」按钮跳入；仅本人 + 完整报告（含 `phase_scores`）允许进入。
- **数据来源**：复用 `analysisService.getReport()` 完整报告 + `analysisService.createShareCard()` 拉小程序码 URL；公开（脱敏）报告无 phase_scores，不挂入口。
- **Canvas 渲染**：
  - 视口外离屏 `Canvas#poster-canvas`（CSS 750×1334 px），`selectorQuery` 拿 `node`；
  - 物理像素按 `pixelRatio`（钳 1~3）放大，`ctx.scale(dpr, dpr)` 让代码以逻辑像素工作；
  - 网络图先 `Taro.getImageInfo` 拿本地 `path`，再 `canvas.createImage()` 注入（小程序新版 Canvas 2D 必须本地 src）；
  - 落地用 `canvasToTempFilePath` 输出 PNG，绑到 `<Image>` 预览。
- **保存到相册**：
  - 已声明 `app.config.ts` permission `scope.writePhotosAlbum`，附 `desc` 文案；
  - 二段授权：先 `Taro.getSetting()` 看 scope，未决 → `authorize`，明确拒绝 → `showModal` 引导 `openSetting`；
  - 任何失败均 toast 兜底，不让用户陷在状态机里。
- **埋点**：成功生成海报 / 点击转发都调一次 `shareService.logShare({ share_type: 'invite_poster', target_id: analysisId })`，复用现有 share-log 表。
- **品牌色合规**：Canvas 不支持 CSS 变量，但所有 HEX 都在 `POSTER_COLORS` 常量里集中维护，与 `app.scss` Design Tokens 一一对齐（白皮书 §7.2）。
- **测试覆盖**：[`posterLayout.test.ts`](../../client/src/utils/__tests__/posterLayout.test.ts) 与 [`posterCanvas.test.ts`](../../client/src/utils/__tests__/posterCanvas.test.ts) 共 49 个用例覆盖几何公式 / 截断 / 评级颜色 / 缺数据兜底；不依赖 jsdom canvas 渲染。

