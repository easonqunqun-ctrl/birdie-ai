"""测试替身：Fake MinIO / Fake AI Engine."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import httpx


class FakeMinioStorage:
    """测试替身。模拟 MinIO 行为但不访问网络。

    - `presign_post_policy`：返回可预期的伪字段。
    - `head_object`：命中 `mark_uploaded` / `put_object_bytes` 后返回 stat，否则返回 None。
    - `mark_uploaded(key, size, content_type)`：测试代码手动标记"对象已上传"。
    """

    bucket = "xiaoniao-videos-test"

    def __init__(self) -> None:
        self._uploaded: dict[str, dict[str, Any]] = {}

    def mark_uploaded(self, key: str, size: int, content_type: str = "video/mp4") -> None:
        self._uploaded[key] = {
            "size": size,
            "etag": "fake-etag",
            "content_type": content_type,
            "last_modified": datetime.now(UTC),
        }

    def presign_post_policy(
        self,
        *,
        key: str,
        content_type: str,
        max_size: int,
        min_size: int = 1,
        expires_in_seconds: int = 3600,
    ) -> tuple[str, dict[str, str], datetime]:
        expires_at = datetime.now(UTC) + timedelta(seconds=expires_in_seconds)
        fields = {
            "policy": "fake-base64-policy",
            "x-amz-algorithm": "AWS4-HMAC-SHA256",
            "x-amz-credential": "fake-credential",
            "x-amz-date": expires_at.strftime("%Y%m%dT%H%M%SZ"),
            "x-amz-signature": "fake-signature",
            "key": key,
            "Content-Type": content_type,
        }
        return f"http://localhost:9000/{self.bucket}", fields, expires_at

    def put_object_bytes(self, *, key: str, data: bytes, content_type: str) -> None:
        self.mark_uploaded(key, len(data), content_type)

    def head_object(self, key: str) -> dict | None:
        return self._uploaded.get(key)

    def get_object_url(self, key: str) -> str:
        return f"http://localhost:9000/{self.bucket}/{key}"

    def presign_get_url(
        self, key: str, *, expires_in_seconds: int = 3600
    ) -> tuple[str, datetime]:
        expires_at = datetime.now(UTC) + timedelta(seconds=expires_in_seconds)
        return f"http://localhost:9000/{self.bucket}/{key}?sig=fake", expires_at


class FakeAIEngine:
    """测试替身：代替 `app.integrations.ai_engine.AIEngineClient`.

    - `set_mode("ok")`：默认，返回完整 mock 报告。
    - `set_mode("engine_failed", code=50102, message="...")`：ai_engine 自己返回 status=failed。
    - `set_mode("timeout")`：每次调用都抛 httpx.TimeoutException（测试重试 + 终态失败）。
    - `set_mode("flaky", succeed_on_attempt=2)`：前 N-1 次抛超时，第 N 次返回 ok（测试重试后成功）。
    """

    def __init__(self) -> None:
        self.mode: Literal["ok", "engine_failed", "timeout", "flaky", "precheck_blocked"] = "ok"
        self.detect_mode: Literal["single", "multi", "overflow", "failed"] = "single"
        self.error_code: int = 50101
        self.error_message: str = "分析失败"
        self.succeed_on_attempt: int = 1
        self._call_count: int = 0
        self.calls: list[dict[str, Any]] = []

    def set_mode(
        self,
        mode: Literal["ok", "engine_failed", "timeout", "flaky", "precheck_blocked"],
        *,
        error_code: int = 50101,
        error_message: str = "分析失败",
        succeed_on_attempt: int = 1,
    ) -> None:
        self.mode = mode
        self.error_code = error_code
        self.error_message = error_message
        self.succeed_on_attempt = succeed_on_attempt
        self._call_count = 0
        self.calls.clear()

    @property
    def call_count(self) -> int:
        return self._call_count

    async def analyze(
        self,
        *,
        analysis_id: str,
        video_url: str,
        camera_angle: str,
        club_type: str,
    ) -> dict:
        self._call_count += 1
        self.calls.append(
            {
                "method": "analyze",
                "analysis_id": analysis_id,
                "video_url": video_url,
                "camera_angle": camera_angle,
                "club_type": club_type,
                "attempt": self._call_count,
            }
        )
        if self.mode == "timeout":
            raise httpx.TimeoutException("fake timeout")
        if self.mode == "flaky" and self._call_count < self.succeed_on_attempt:
            raise httpx.TimeoutException("fake flaky")
        if self.mode == "engine_failed":
            return {
                "analysis_id": analysis_id,
                "status": "failed",
                "error_code": self.error_code,
                "error_message": self.error_message,
            }
        # ok: 返回一组稳定的假结果
        return _build_ok_result(analysis_id, video_url, club_type)

    async def precheck(
        self,
        *,
        analysis_id: str,
        video_url: str,
    ) -> dict:
        self.calls.append(
            {
                "method": "precheck",
                "analysis_id": analysis_id,
                "video_url": video_url,
            }
        )
        if self.mode == "precheck_blocked":
            return {
                "analysis_id": analysis_id,
                "status": "blocked",
                "quality_warnings": [],
                "error_code": self.error_code,
                "error_message": self.error_message,
                "elapsed_ms": 120,
                "scan_elapsed_ms": 80,
            }
        return {
            "analysis_id": analysis_id,
            "status": "passed",
            "quality_warnings": [],
            "elapsed_ms": 50,
            "scan_elapsed_ms": 40,
        }

    async def detect_swings(
        self,
        *,
        analysis_id: str,
        video_url: str,
    ) -> dict:
        self.calls.append(
            {
                "method": "detect_swings",
                "analysis_id": analysis_id,
                "video_url": video_url,
            }
        )
        if self.detect_mode == "overflow":
            return {
                "analysis_id": analysis_id,
                "status": "failed",
                "error_code": 50122,
                "error_message": "检测到超过 5 段挥杆，请重拍 1-3 段",
            }
        if self.detect_mode == "failed":
            return {
                "analysis_id": analysis_id,
                "status": "failed",
                "error_code": self.error_code,
                "error_message": self.error_message,
            }
        if self.detect_mode == "multi":
            return {
                "analysis_id": analysis_id,
                "status": "ok",
                "swing_candidates": [
                    {
                        "start_frame": 30,
                        "end_frame": 120,
                        "is_practice": True,
                        "confidence": 0.88,
                        "start_time_sec": 1.0,
                        "end_time_sec": 4.0,
                        "preview_frame_url": "http://minio.local/bucket/keyframes/upl_x/swing_0.jpg",
                    },
                    {
                        "start_frame": 180,
                        "end_frame": 270,
                        "is_practice": False,
                        "confidence": 0.95,
                        "start_time_sec": 6.0,
                        "end_time_sec": 9.0,
                        "preview_frame_url": "http://minio.local/bucket/keyframes/upl_x/swing_1.jpg",
                    },
                ],
                "default_selected_index": 1,
            }
        return {
            "analysis_id": analysis_id,
            "status": "ok",
            "swing_candidates": [
                {
                    "start_frame": 30,
                    "end_frame": 120,
                    "is_practice": False,
                    "confidence": 0.95,
                    "start_time_sec": 1.0,
                    "end_time_sec": 4.0,
                }
            ],
            "default_selected_index": 0,
        }


def _build_ok_result(analysis_id: str, video_url: str, club_type: str) -> dict:
    """合成一份"长得像 AI Engine 正常返回"的 dict，覆盖后端落库所有字段。"""
    return {
        "analysis_id": analysis_id,
        "status": "completed",
        "overall_score": 78,
        "phase_scores": {
            "setup": {"score": 85, "label": "站位准备", "is_weakest": False},
            "backswing": {"score": 75, "label": "上杆轨迹", "is_weakest": False},
            "top": {"score": 80, "label": "顶点位置", "is_weakest": False},
            "downswing": {"score": 65, "label": "下杆转换", "is_weakest": True},
            "impact": {"score": 78, "label": "击球触球", "is_weakest": False},
            "follow_through": {"score": 82, "label": "收杆平衡", "is_weakest": False},
        },
        "phase_timestamps": {
            "setup": {"start": 0.0, "end": 0.8},
            "backswing": {"start": 0.8, "end": 1.5},
            "top": {"start": 1.5, "end": 1.7},
            "downswing": {"start": 1.7, "end": 2.0},
            "impact": {"start": 2.0, "end": 2.1},
            "follow_through": {"start": 2.1, "end": 2.8},
        },
        "issues": [
            {
                "type": "casting",
                "name": "抛杆（Casting）",
                "severity": "high",
                "description": "下杆初期手腕过早释放。",
                "key_frame_timestamp": 1.8,
            },
            {
                "type": "early_extension",
                "name": "提前伸展",
                "severity": "medium",
                "description": "髋部过早向球方向移动。",
                "key_frame_timestamp": 1.9,
            },
        ],
        "recommendations": [
            {
                "drill_id": "drill_towel_arm",
                "name": "毛巾夹臂练习",
                "target_issue": "casting",
                "description": "修复手腕过早释放",
                "duration_minutes": 15,
                "sets": 3,
                "steps": ["步骤1", "步骤2"],
            },
        ],
        "skeleton_video_url": video_url.replace(".mp4", "_skeleton.mp4"),
        "thumbnail_url": video_url.replace(".mp4", "_thumb.jpg"),
        "duration_ms": 3200,
    }
