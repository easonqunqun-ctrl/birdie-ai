# AI Engine

视觉分析引擎（独立服务）。

## 模式

- **mock 模式（默认）**：返回符合 schema 的随机报告，2-5 秒延迟。`AI_ENGINE_MOCK_MODE=true`
- **真实模式（W6）**：接入 MediaPipe + 评分规则。`AI_ENGINE_MOCK_MODE=false`

## 接口

- `GET /health` 健康检查
- `POST /analyze` 执行分析
- `GET /docs` Swagger UI

## 本地启动

随主项目一起：`make up`，访问 <http://localhost:9000/docs>。

单独启动：

```bash
cd ai_engine
uv sync
uv run uvicorn app.main:app --reload --port 9000
```
