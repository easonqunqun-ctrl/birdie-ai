# W10 React Native · 里程碑拆分（支付与订阅降级优先）

> 总览能力矩阵：[**`W10-weapp-apis-rn-matrix.md`**](W10-weapp-apis-rn-matrix.md) · 规划正文：[**`docs/18-W10-RN-App端规划.md`**](../18-W10-RN-App端规划.md)。  
> [`docs/19-产品开发迭代计划-当前队列.md`](../19-产品开发迭代计划-当前队列.md) **Q-D1**。

## Milestone RN-1 · 运行时与网络（P0）

- Taro RN shell 与本仓库 `pnpm`/`make client-check-rn` 对齐；`request.ts` / SSE 通路 smoke。
- 媒体 adapter：`capture`/`upload`/`download` 等价路径在无微信 API 下可降级。

## Milestone RN-2 · 商业（P0）

- **支付**：`Taro.requestPayment` → IAP 或其他渠道产品设计拍板后再接；会员状态仍以后端 `/users/me` 为准。
- **订阅消息**：无微信 runtime → **本地推送占位**或「请至小程序订阅」静默跳过（已由 matrix 标明）。

## Milestone RN-3 · UI 对等（P1）

- RadarChart：`createSelectorQuery` 替换 RN 图表实现（参见 matrix）。
- Tab / 路由与微信小程序 IA 对齐，占位页仍以文档排期为准。

每条里程碑结束条件：**CI RN bundle + 真机 smoke 清单** [`W10-rn-smoke-checklist.md`](W10-rn-smoke-checklist.md)。
