"""Distinguish client audit events from legacy status transitions."""

from alembic import op
import sqlalchemy as sa

revision = "012_business_audit"
down_revision = "011_platform_admin"


def upgrade():
    op.add_column("audit_logs", sa.Column("action", sa.String(32), nullable=False, server_default="status_changed"))
    op.create_check_constraint(
        "ck_audit_logs_action", "audit_logs",
        "action IN ('status_changed','created','uploaded','parsed','deleted','previewed','downloaded','settings_updated')",
    )


def downgrade():
    op.drop_constraint("ck_audit_logs_action", "audit_logs", type_="check")
    op.drop_column("audit_logs", "action")
