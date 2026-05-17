# W8 分享与邀请 · Roadmap（海报 / 小程序码）

> MVP [`docs/01` §7](../01-MVP功能需求规格说明书.md) 延后项；当前主线为原生 `openType='share'` + 复制邀请码。**本文件仅列开发队列，不写实现臆测**。

## 队列

| 阶段 | 项 | 说明 |
|------|-----|------|
| P1 | `wxacode.getUnlimited` / 服务端生成小程序码 | 后端 endpoint + COS/缓存 TTL；与 **`invite_code` 扫码 deep link** 对齐 |
| P1 | 750×1334 分享海报 Canvas | report 页离屏绘图 + 骨骼缩略雷达；与品牌色变量对齐 `app.scss` |
| P2 | 朋友圈封面 / 小程序码嵌入邀请记录页 | §7 Checkbox |
| — | OSS/CDN URL | COS 静态资源域名与 CDN 缓存策略（见 **`W9-code-vs-plan-status`**）|

契约：`POST /v1/analyses/{id}/share-card` 或独立 `/shares/wxa-code` 若落地须先更新 [**`docs/02`**](../02-API接口设计文档.md)。
