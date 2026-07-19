# W10 React Native · 里程碑拆分（支付与订阅降级优先）

> 总览能力矩阵：[**`W10-weapp-apis-rn-matrix.md`**](W10-weapp-apis-rn-matrix.md) · 规划正文：[**`docs/18-W10-RN-App端规划.md`**](../18-W10-RN-App端规划.md)。  
> [`docs/19-产品开发迭代计划-当前队列.md`](../19-产品开发迭代计划-当前队列.md) **Q-D1**。  
> **开工执行面（勾选真源）**：[**`app-m0-m1-kickoff-checklist.md`**](app-m0-m1-kickoff-checklist.md)（M0 / 帧率 Spike / M1 / 性能三项）。

## 与 M0 / M1 映射

| 本文件里程碑 | 开工清单 | 说明 |
|--------------|----------|------|
| **RN-1** | **M0**（+ M0-3 登录） | shell、request、SSE、媒体降级路径 |
| **RN-2** | 清单 §7 降级 | 本周期保持支付/订阅降级，不阻塞 M1 |
| **RN-3** | **M1** | 雷达 / Tab / 报告 UI 对等 |
| （Q-D2 前置） | **SP-1 / SP-2** | 三组帧率 Spike；不做弹道成片 |
| （体验优势） | **P-1～P-3** | 拍摄 / 弱网上传 / scrub，与 M1 重叠验 |

## Milestone RN-1 · 运行时与网络（P0）

- Taro RN shell 与本仓库 `pnpm`/`make client-check-rn` 对齐；`request.ts` / SSE 通路 smoke。
- 媒体 adapter：`capture`/`upload`/`download` 等价路径在无微信 API 下可降级。
- 勾选：开工清单 **M0-1～M0-5**。

## Milestone RN-2 · 商业（P0）

- **支付**：`Taro.requestPayment` → IAP 或其他渠道产品设计拍板后再接；会员状态仍以后端 `/users/me` 为准。
- **订阅消息**：无微信 runtime → **本地推送占位**或「请至小程序订阅」静默跳过（已由 matrix 标明）。
- 勾选：开工清单 §7（本周期维持降级即可标 Done）。

## Milestone RN-3 · UI 对等（P1）

- RadarChart：`createSelectorQuery` 替换 RN 图表实现（参见 matrix）。
- Tab / 路由与微信小程序 IA 对齐，占位页仍以文档排期为准。
- 勾选：开工清单 **M1-1～M1-5** + §5 性能三项（至少两项有记录）。

每条里程碑结束条件：**CI RN bundle + 真机 smoke 清单** [`W10-rn-smoke-checklist.md`](W10-rn-smoke-checklist.md) + 开工清单对应勾项。
