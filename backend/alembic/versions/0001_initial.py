"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "work_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("component_id", sa.String(128), nullable=False),
        sa.Column(
            "component_type",
            sa.Enum("RDBMS", "NOSQL", "CACHE", "API", "QUEUE", "MCP_HOST", name="componenttype"),
            nullable=False,
            server_default="API",
        ),
        sa.Column(
            "status",
            sa.Enum("OPEN", "INVESTIGATING", "RESOLVED", "CLOSED", name="workitemstatus"),
            nullable=False,
            server_default="OPEN",
        ),
        sa.Column(
            "priority",
            sa.Enum("P0", "P1", "P2", "P3", name="priority"),
            nullable=False,
            server_default="P2",
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("signal_count", sa.Integer, nullable=False, server_default="1"),
        sa.Column("mttr_seconds", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_work_items_component_id", "work_items", ["component_id"])
    op.create_index("ix_work_items_status", "work_items", ["status"])

    op.create_table(
        "rcas",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "work_item_id",
            sa.String(36),
            sa.ForeignKey("work_items.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("incident_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("incident_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "root_cause_category",
            sa.Enum(
                "HARDWARE_FAILURE", "SOFTWARE_BUG", "CONFIGURATION_ERROR",
                "CAPACITY_EXHAUSTION", "NETWORK_ISSUE", "DEPENDENCY_FAILURE",
                "HUMAN_ERROR", "UNKNOWN",
                name="rootcausecategory",
            ),
            nullable=False,
        ),
        sa.Column("root_cause_description", sa.Text, nullable=False),
        sa.Column("fix_applied", sa.Text, nullable=False),
        sa.Column("prevention_steps", sa.Text, nullable=False),
        sa.Column("submitted_by", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_rcas_work_item_id", "rcas", ["work_item_id"])


def downgrade() -> None:
    op.drop_table("rcas")
    op.drop_index("ix_work_items_status", "work_items")
    op.drop_index("ix_work_items_component_id", "work_items")
    op.drop_table("work_items")
    op.execute("DROP TYPE IF EXISTS workitemstatus")
    op.execute("DROP TYPE IF EXISTS priority")
    op.execute("DROP TYPE IF EXISTS componenttype")
    op.execute("DROP TYPE IF EXISTS rootcausecategory")
