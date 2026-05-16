# W9 · 腾讯云采购清单（领翼golf）

> 小程序名称：领翼golf  
> 主体：北京思无界控股有限公司  
> 微信支付商户号：1111660404  
> 状态：小程序已备案；域名 / ICP / 云资源待确认  
> 目标：支撑 MVP 正式上线（约 100-1000 DAU），先稳后省，避免过早上复杂 K8s。

---

## 一、推荐采购结论

### 首发推荐档位

**腾讯云 CVM + 托管 PostgreSQL + 托管 Redis + COS/CDN + CLB/SSL**

不建议首发直接上 TKE。当前业务体量和团队运维阶段，CVM + Docker Compose 更快、更稳、更好排障；等 DAU / 分析量上来再迁 TKE。

---

## 二、必买清单（MVP 正式上线）

| 类别 | 腾讯云产品 | 推荐规格 | 数量 | 用途 | 预估月费 |
|---|---|---:|---:|---|---:|
| 云服务器 | CVM 标准型 / SA 系列 | 4 核 8G，100G 高性能云硬盘，Ubuntu 22.04 LTS | 2 台 | backend / ai_engine / celery 分离部署或主备 | ¥400-800 |
| 数据库 | TencentDB for PostgreSQL | 2 核 4G，100G 存储，高可用版 | 1 套 | 业务主库 | ¥500-900 |
| 缓存 | TencentDB for Redis | 1G 标准版 | 1 套 | 登录、access_token、队列/缓存 | ¥80-150 |
| 对象存储 | COS 标准存储 | 100G 起 | 1 个 bucket | 原始视频、关键帧、缩略图 | ¥50-200 |
| CDN | 腾讯云 CDN | 按量计费，1TB/月预算 | 1 套 | 图片/视频加速 | ¥100-200 |
| 负载均衡 | CLB 公网型 | HTTPS 监听，带宽 1-5Mbps 起 | 1 个 | `api` 入口、健康检查、后端反代 | ¥50-150 |
| 域名解析 | DNSPod | 免费版或专业版 | 1 套 | DNS 解析 | ¥0-20 |
| SSL 证书 | 腾讯云 SSL 免费 DV / Let's Encrypt | 单域名或泛域名 | 若干 | HTTPS | ¥0 |
| 日志 | CLS 日志服务 | 按量，7-14 天保留 | 1 套 | 后端/AI/支付回调日志 | ¥20-100 |
| 监控告警 | 云监控 + 告警短信/企微 | 免费 + 少量短信 | 1 套 | CPU/内存/接口错误告警 | ¥0-50 |

**首月预算**：约 **¥1200-2500/月**。  
若买包年 CVM 可明显降低月摊成本。

---

## 三、域名与子域名建议

建议尽快注册 / 确认主域名。品牌已改为「领翼golf」，优先考虑：

- `lingyigolf.com`
- `lingyigolf.cn`
- `lingyigolf.com.cn`

正式子域名规划：

| 子域名 | 指向 | 小程序后台配置类型 |
|---|---|---|
| `api.lingyigolf.com` | CLB → backend | request 合法域名 |
| `upload.lingyigolf.com` | CLB / COS 上传入口 | uploadFile 合法域名 |
| `video.lingyigolf.com` | COS + CDN | downloadFile 合法域名 |
| `cdn.lingyigolf.com` | COS + CDN | downloadFile 合法域名 |
| `www.lingyigolf.com` | 官网 / 审核说明页 | web-view 业务域名（后续） |

> 小程序后台不要再配置 cloudflared / trycloudflare 域名；W9 正式包必须全切正式域名。

---

## 四、服务器部署建议

### 首发两台 CVM

| 机器 | 规格 | 部署内容 |
|---|---|---|
| `ly-prod-app-01` | 4C8G / 100G | backend + nginx / API 网关 |
| `ly-prod-ai-01` | 4C8G / 100G | ai_engine + celery-worker |

这样做的好处：

- AI 推理吃 CPU / 内存，不拖慢 API 响应。
- 后端重启不影响 AI 引擎长任务。
- 后续可以横向加 `ly-prod-ai-02`。

### 不建议首发单机全部塞一起

可以省钱，但视频分析时 CPU/内存抖动会影响登录、报告、支付回调。正式上线不建议。

---

## 五、安全组放行

| 端口 | 来源 | 用途 |
|---|---|---|
| 22 | 你的固定 IP | SSH |
| 80 | 全网 | HTTP → HTTPS 跳转 / Let's Encrypt |
| 443 | 全网 | HTTPS API |
| 5432 | 仅 CVM 内网 / 数据库白名单 | PostgreSQL |
| 6379 | 仅 CVM 内网 / Redis 白名单 | Redis |
| 8000 / 9000 / 9100 | 不对公网开放 | backend / MinIO / ai_engine 内部端口 |

---

## 六、COS Bucket 规划

| Bucket / 前缀 | 用途 | 权限 |
|---|---|---|
| `lingyi-golf-prod` | 生产资源 bucket | 私有读写 |
| `uploads/` | 原始挥杆视频 | 私有 |
| `keyframes/` | 关键帧图片 | 私有，CDN 签名 URL 或后端代理 |
| `thumbnails/` | 报告缩略图 / 分享图 | 可 CDN 访问 |
| `share-cards/` | 分享卡封面 | 可 CDN 访问 |

建议先走**后端签名上传 / 后端代理读取**，上线稳定后再做客户端 STS 直传优化。

---

## 七、微信支付参数落地

已知：

| 项 | 值 |
|---|---|
| 商户号 | `1111660404` |
| 主体 | 北京思无界控股有限公司 |

还需准备并填入生产环境变量：

```env
WECHAT_PAY_MCH_ID=1111660404
WECHAT_PAY_API_V3_KEY=...
WECHAT_PAY_MCH_SERIAL_NO=...
WECHAT_PAY_PRIVATE_KEY_PATH=/run/secrets/wechatpay_apiclient_key.pem
WECHAT_PAY_NOTIFY_URL=https://api.lingyigolf.com/v1/payments/wechat/notify
PAYMENT_ENABLED=true
PAYMENT_MOCK=false
```

---

## 八、正式环境变量切换

```env
APP_ENV=prod
WECHAT_MOCK_LOGIN=false
QUOTA_MODE=strict
PAYMENT_ENABLED=true
PAYMENT_MOCK=false
LLM_PROVIDER=deepseek
MINIO_PUBLIC_ENDPOINT=
COS_BUCKET=lingyi-golf-prod
COS_REGION=ap-beijing
API_PUBLIC_BASE_URL=https://api.lingyigolf.com
```

客户端：

```env
TARO_APP_API_BASE_URL=https://api.lingyigolf.com/v1
TARO_APP_PAYMENT_ENABLED=true
TARO_APP_PAYMENT_MOCK=false
TARO_APP_DEBUG=false
```

---

## 九、可暂缓采购

| 产品 | 暂缓原因 |
|---|---|
| TKE | 首发运维成本高，CVM + Compose 足够 |
| GPU 云服务器 | MediaPipe CPU 版先跑，按分析耗时再决定 |
| WAF | 首发可先用 CLB + 安全组 + 限流，用户量起来再加 |
| 高级 APM | 先用 CLS + events 表 + 后端日志 |
| 运营后台 | 首发用 SQL / 脚本运营即可 |

---

## 十、采购顺序

1. 注册 / 确认域名，并补齐 ICP 备案状态。
2. 购买 TencentDB PostgreSQL + Redis。
3. 购买 2 台 CVM。
4. 购买 / 配置 CLB + SSL。
5. 创建 COS bucket + CDN 域名。
6. 小程序后台配置合法域名。
7. 写入生产 `.env.production` / 服务器 `.env.local`。
8. 部署生产栈，先用白名单账号走 W8 全流程补测。

