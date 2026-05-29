#!/usr/bin/env python3
"""M8-10 · 为种子教练开通一年高级会员权益.

用法（仓库根目录）::

    cd backend && uv run python ../tools/scripts/grant_seed_coach_premium.py --coach-id usr_xxx
    cd backend && uv run python ../tools/scripts/grant_seed_coach_premium.py --coach-id usr_xxx --days 365
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2] / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


async def _run(coach_id: str, days: int) -> None:
    from app.core.database import AsyncSessionLocal
    from app.services.coach_seed_service import grant_seed_premium

    async with AsyncSessionLocal() as db:
        result = await grant_seed_premium(
            db,
            admin=None,
            coach_user_id=coach_id,
            valid_days=days,
        )
        await db.commit()
    print(
        f"OK user={result.user_id} membership={result.membership_type} "
        f"expires={result.membership_expires_at.isoformat()} (+{result.granted_days}d)"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Grant seed coach premium membership")
    parser.add_argument("--coach-id", required=True, help="Coach user_id")
    parser.add_argument("--days", type=int, default=365, help="Valid days (default 365)")
    args = parser.parse_args()
    asyncio.run(_run(args.coach_id, args.days))


if __name__ == "__main__":
    main()
