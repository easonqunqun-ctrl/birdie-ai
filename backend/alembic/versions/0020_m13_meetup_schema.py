"""M13 P2-M13-01 约球 5 张表.

逻辑编号：docs/03 §8.7 规划 0013-0014；实际落库编号：0020（按 alembic head 续编：
M9-01=0017, M11-01=0018, M12-01=0019 → 0020）。

revision: 0020_m13_meetup_schema
down_revision: 0019_m12_pro_library_schema
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0020_m13_meetup_schema"
down_revision: Union[str, None] = "0019_m12_pro_library_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---------- venues ----------
    op.create_table(
        "venues",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("city", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("venue_type", sa.String(length=20), nullable=False),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column(
            "source",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'ugc'"),
        ),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
        sa.Column(
            "contributor_user_id",
            sa.String(length=32),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint(
            "venue_type IN ('indoor_range', 'outdoor_range', 'simulator_lounge', 'golf_course')",
            name="chk_venue_type",
        ),
        sa.CheckConstraint(
            "source IN ('ugc', 'verified')",
            name="chk_venue_source",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'flagged', 'closed')",
            name="chk_venue_status",
        ),
    )
    op.create_index("idx_venues_city_status", "venues", ["city", "status"])

    # ---------- meetup_invitations ----------
    op.create_table(
        "meetup_invitations",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column(
            "inviter_user_id",
            sa.String(length=32),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "invitee_user_id",
            sa.String(length=32),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "venue_id",
            sa.String(length=32),
            sa.ForeignKey("venues.id"),
            nullable=True,
        ),
        sa.Column("proposed_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column(
            "contact_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "risk_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'accepted', 'declined', 'expired', 'cancelled')",
            name="chk_mvi_status",
        ),
        sa.CheckConstraint(
            "inviter_user_id != invitee_user_id",
            name="chk_no_self_invite",
        ),
    )
    op.create_index(
        "idx_mvi_invitee_status",
        "meetup_invitations",
        ["invitee_user_id", "status"],
    )
    op.create_index(
        "idx_mvi_inviter_status",
        "meetup_invitations",
        ["inviter_user_id", "status"],
    )

    # ---------- meetup_feedbacks ----------
    op.create_table(
        "meetup_feedbacks",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column(
            "invitation_id",
            sa.String(length=32),
            sa.ForeignKey("meetup_invitations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "reviewer_user_id",
            sa.String(length=32),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "reviewee_user_id",
            sa.String(length=32),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("rating", sa.SmallInteger(), nullable=False),
        sa.Column(
            "tags",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "credit_delta",
            sa.Numeric(5, 2),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "is_visible",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("TRUE"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint("rating BETWEEN 1 AND 5", name="chk_mfb_rating"),
        sa.CheckConstraint(
            "credit_delta BETWEEN -10 AND 10",
            name="chk_mfb_credit_delta",
        ),
        sa.CheckConstraint(
            "reviewer_user_id != reviewee_user_id",
            name="chk_mfb_no_self",
        ),
    )
    op.create_index(
        "idx_mfb_reviewee",
        "meetup_feedbacks",
        ["reviewee_user_id", "created_at"],
    )

    # ---------- self_organized_events ----------
    op.create_table(
        "self_organized_events",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column(
            "organizer_user_id",
            sa.String(length=32),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "venue_id",
            sa.String(length=32),
            sa.ForeignKey("venues.id"),
            nullable=True,
        ),
        sa.Column("title", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("template_code", sa.String(length=40), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("capacity", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'draft'"),
        ),
        sa.Column("badge_template_code", sa.String(length=40), nullable=True),
        sa.Column(
            "rules_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "moderation_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'open', 'closed', 'cancelled', 'completed')",
            name="chk_soe_status",
        ),
        sa.CheckConstraint(
            "capacity IS NULL OR (capacity BETWEEN 1 AND 200)",
            name="chk_soe_capacity",
        ),
    )
    op.create_index(
        "idx_soe_status_time",
        "self_organized_events",
        ["status", "scheduled_at"],
    )

    # ---------- event_participations ----------
    op.create_table(
        "event_participations",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column(
            "event_id",
            sa.String(length=32),
            sa.ForeignKey("self_organized_events.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.String(length=32),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'signed_up'"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint(
            "status IN ('signed_up', 'checked_in', 'completed', 'no_show', 'cancelled')",
            name="chk_evp_status",
        ),
    )
    op.create_index(
        "idx_evp_event_status",
        "event_participations",
        ["event_id", "status"],
    )
    op.create_index(
        "idx_evp_user",
        "event_participations",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_evp_user", table_name="event_participations")
    op.drop_index("idx_evp_event_status", table_name="event_participations")
    op.drop_table("event_participations")
    op.drop_index("idx_soe_status_time", table_name="self_organized_events")
    op.drop_table("self_organized_events")
    op.drop_index("idx_mfb_reviewee", table_name="meetup_feedbacks")
    op.drop_table("meetup_feedbacks")
    op.drop_index("idx_mvi_inviter_status", table_name="meetup_invitations")
    op.drop_index("idx_mvi_invitee_status", table_name="meetup_invitations")
    op.drop_table("meetup_invitations")
    op.drop_index("idx_venues_city_status", table_name="venues")
    op.drop_table("venues")
