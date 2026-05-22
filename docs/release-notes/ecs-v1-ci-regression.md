# ECS v1 CI 回归（ENG-04）

ENG-04 的第一条可执行回归：对 `tests/ecs/v1/manifest.json` 中合成 Pose 样本跑 scoring 子链路，与 `baseline_snapshot.json` 对比漂移，并应用 [`ecs-v1-starter-checklist.md`](../ecs-v1-starter-checklist.md) §4 门禁阈值。

> **注意**：当前 manifest 为 **`v1-ci-stub`**（合成 Pose，非授权顶尖素材）。真 ECS 满编后替换 manifest 并重新生成 baseline，并恢复 `teaching_overall_floor=80` 硬门禁。

## 本地运行

```bash
cd ai_engine
uv run pytest tests/test_ecs_regression.py -v
# 或
uv run python scripts/generate_ecs_baseline.py   # 更新 baseline_snapshot.json
```

## CI

GitHub Actions：`.github/workflows/ai-engine-ecs-regression.yml`（Python 3.11 + `uv sync`）。

## 漂移阈值（默认）

| 级别 | 条件 |
|------|------|
| yellow | 单条 overall Δ > ±5；单维 Δ > ±8 |
| red | teaching 标杆 overall < 80；≥50% 样本同向 overall Δ > ±3 |

CI stub 跑回归时将 `teaching_overall_floor=0`（见 `test_ecs_regression.py`）。
