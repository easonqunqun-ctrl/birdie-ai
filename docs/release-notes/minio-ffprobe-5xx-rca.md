# MinIO ffprobe 5XX 根因分析与治理

> 关联：P2-W12-3（监控/重试）+ P2-W13-C（根治）
> 状态：W13-C 修复已合入 `_rewrite_to_internal_url`

## 1 · 背景

W10 期间发现 AI 引擎 `_probe_video_warnings` 调 `ffprobe URL` 时偶发：

```
Server returned 5XX Server Error reply
```

具体表现为 `v2_probe_count` 上涨的同时 `v2_probe_errors` 同步上涨，但用户视频本身能在客户端 `<Video>` 中播放——说明 MinIO 对象本身没坏，只是 **ffprobe 这一路** 偶发 5xx。

W12-3 在症状层做了 retry + 错误分类 + observability（5xx/timeout 2 次指数退避，4xx 不 retry），但根因没动；本文档给出架构层根因 + 治本修复。

## 2 · 链路全貌

### 2.1 客户端上传 → backend 写库

```
微信小程序 -- presigned POST --> nginx /minio/ → minio:9000
                                                       |
                                                       v
                                         backend `to_proxy_video_url(get_object_url(key))`
                                         → `https://api.birdieai.cn/minio/<bucket>/<key>`
                                         (公网 URL，无签名；bucket 设了 anonymous download)
                                                       |
                                                       v
                                              DB.swing_analysis.video_url
```

### 2.2 Celery → ai_engine `_probe_video_warnings`

```
celery-worker --(httpx /analyze, body 含 req.video_url=公网 URL)--> ai_engine:9000
                                                                            |
                                                                            v
                                            real_pipeline_v2._probe_video_warnings(req.video_url)
                                                |
                                                v
                                  ffprobe -i "https://api.birdieai.cn/minio/<bucket>/<key>"
                                                |  ← 这一步是 5xx 来源
                                                v
                                  ai_engine 容器 → 公网 DNS → CVM nginx 443 → /minio/ → minio:9000
                                  (4 跳：HTTPS 握手 + nginx 反代 + docker bridge + minio)
```

**反模式**：ai_engine **和** MinIO 在同一台 CVM 同一个 docker network 里，但 ffprobe 却绕了一圈公网。

## 3 · 5XX 候选原因（按概率排序）

| 原因 | 触发条件 | 证据 |
|---|---|---|
| **A · nginx `/minio/` 不 retry 5xx** | MinIO 临时高负载（GC / disk flush / 别的请求挤占）→ 偶发 503 → nginx 直接透传 | nginx `proxy_next_upstream` 默认仅 `error timeout`，不含 `http_5xx` |
| B · MinIO 默认 max 连接数被打满 | 并发上传 + 并发 probe 同时压在 minio:9000 | MinIO 单实例 `--api requests-max` 默认 1024 |
| C · CVM 公网入口竞争 | nginx 同时处理别的 /v1/ 请求 + /minio/ 反代，公网带宽峰值挤占 | access.log 高峰期 502 集中 |
| D · ffprobe HTTP/2 兼容 | nginx 启用 `http2 on`，ffprobe 默认 HTTP/1.1 — 可降级但延迟波动 | 调查中（W18+ 验） |

**根本性问题**：所有 4 个原因都**只在公网路径上才存在**。ai_engine ↔ MinIO 应该走 docker 内网，绕开 nginx 全部 4 跳。

## 4 · 修复方案

### 4.1 W12-3（症状治理 · 已落地）

| 改动 | 文件 | 效果 |
|---|---|---|
| 5xx/timeout 指数退避 retry 2 次 | `_probe_with_retry` | 临时抖动恢复 |
| 错误分类（5xx / 4xx / timeout / binary_missing / unknown） | `_classify_probe_error` | dashboard 可拆桶看 |
| 失败时返回 `probe_failed` engine_warning（不再静默） | `_probe_video_warnings` | 客户端 W10 调试浮层能看到 |
| URL log 脱敏（去 query string） | `_sanitize_probe_url` | 防 `X-Amz-Signature` 泄漏 |
| 6 个分桶 metrics | `metrics.py` | Prometheus 可告警 |

### 4.2 W13-C（根治 · 本次）

**核心**：`_rewrite_to_internal_url(url)` — 把 `settings.MINIO_PUBLIC_ENDPOINT` 前缀替换为 `settings.MINIO_ENDPOINT`，让 ffprobe 走 docker 内网。

```python
# real_pipeline_v2.py
def _rewrite_to_internal_url(url: str) -> str:
    pub = settings.MINIO_PUBLIC_ENDPOINT.rstrip("/")
    internal = settings.MINIO_ENDPOINT.rstrip("/")
    if not pub or not internal or pub == internal:
        return url
    if not url.startswith(pub + "/"):
        return url
    return internal + url[len(pub):]
```

例子：

```
input  : https://api.birdieai.cn/minio/xiaoniao-videos/uploads/abc.mp4
            └─ MINIO_PUBLIC_ENDPOINT = https://api.birdieai.cn/minio ─┘
output : http://minio:9000/xiaoniao-videos/uploads/abc.mp4
            └─ MINIO_ENDPOINT = http://minio:9000 ─┘
```

**链路缩短**：

```
之前: ai_engine → 公网 DNS → CVM nginx 443 → /minio/ → minio:9000   (4 跳)
之后: ai_engine → docker 内网 → minio:9000                             (1 跳)
```

**兼容性**：

- URL 不在 `MINIO_PUBLIC_ENDPOINT` 前缀下（COS / 第三方 / sample fixture URL）→ 原样返回，仍走 W12-3 retry 兜底
- `MINIO_PUBLIC_ENDPOINT == MINIO_ENDPOINT`（开发本机）→ 原样返回
- 任一 endpoint 缺失 → 原样返回

### 4.3 W13-C 不动的事

- **不**改 nginx `/minio/` 路径 — 客户端 `<Video>` 仍要用它，不能下线
- **不**改 backend `to_proxy_video_url` — DB 入库 URL 仍是公网，符合"客户端可直接播"约定
- **不**在 ai_engine 加 MinIO SDK — ffprobe 只读 metadata，不需要 SDK 鉴权，直接 HTTP GET 就行
- **不**改 `MINIO_PUBLIC_ENDPOINT` 默认值（兼容现有 `.env.local`）

## 5 · 验证

### 5.1 本地单测（ai_engine）

```
pytest tests/test_real_pipeline_v2_probe.py -k url_rewrite -v
```

覆盖：

- URL 命中 public 前缀 → 改写
- URL 不命中（COS / 第三方）→ 原样返回
- endpoint 缺失 → 原样返回
- public == internal（开发） → 原样返回
- end-to-end `_probe_video_warnings` 实际拿到的是 internal URL（mock ffprobe assert）

### 5.2 CVM 验证（上线后 24h 观察）

```
curl -sS http://localhost:9100/metrics | jq '{
  count: .v2_probe_count,
  errors: .v2_probe_errors,
  rate: .v2_probe_error_rate,
  retries: .v2_probe_retries,
  by_reason: {
    "5xx": .v2_probe_errors_5xx_after_retries,
    "timeout": .v2_probe_errors_timeout_after_retries,
    "4xx": .v2_probe_errors_4xx,
    "binary": .v2_probe_errors_binary_missing,
    "unknown": .v2_probe_errors_unknown
  }
}'
```

**预期变化**：

| 指标 | W12-3（仅 retry） | W13-C（内网直连） |
|---|---|---|
| `v2_probe_error_rate` | ≤ 5%（retry 救回大部分） | **≤ 0.5%** |
| `v2_probe_errors_5xx_after_retries` | > 0 | **≈ 0** |
| `v2_probe_retries` | 与 5xx_after_retries 同向 | **≈ 0** |

如果上线一周仍看到 5xx，说明根因不在 nginx，而是 MinIO 自身（候选 B），转 W14 治。

## 6 · 后续 backlog（暂不做）

- **W14 候选**：MinIO 单实例升级为 `--api requests-max=4096` + 监控 `minio_s3_requests_inflight`
- **W18 候选**：把 video_url 改成"上传成功后即返内网 + 公网双 URL"模式，ai_engine 直接用内网字段，无需重写
- **prod 候选**：CVM → TKE 后 MinIO 用 distributed mode 4 节点，5xx 概率指数级降低
