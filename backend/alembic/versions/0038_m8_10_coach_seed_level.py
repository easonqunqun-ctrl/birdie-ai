"""M8-10 · coach_profiles.level 追加 seed 枚举.

revision: 0038_m8_10_coach_seed_level
down_revision: 0037_m8_08_moderation_queue
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0038_m8_10_coach_seed_level"
down_revision: Union[str, None] = "0037_m8_08_moderation_queue"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("chk_cp_level", "coach_profiles", type_="check")
    op.create_check_constraint(
        "chk_cp_level",
        "coach_profiles",
        "level IN ('pga', 'china_pga', 'regional', 'club_pro', 'seed')",
    )


def downgrade() -> None:
    op.drop_constraint("chk_cp_level", "coach_profiles", type_="check")
    op.create_check_constraint(
        "chk_cp_level",
        "coach_profiles",
        "level IN ('pga', 'china_pga', 'regional', 'club_pro')",
    )
