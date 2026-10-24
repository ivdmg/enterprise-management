"""Add missing audit table and dispatch incident fields."""
from alembic import op
import sqlalchemy as sa

revision = "004_audit_dispatch"
down_revision = "003_drive_sources"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("audit_logs",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("company_id", sa.UUID(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.UUID(), nullable=False),
        sa.Column("old_status", sa.String(100)),
        sa.Column("new_status", sa.String(100), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("ip_address", sa.String(100)),
        sa.Column("user_agent", sa.String(500)),
    )
    op.create_index("idx_audit_logs_company_entity", "audit_logs", ["company_id", "entity_type", "entity_id"])
    op.create_index("idx_audit_logs_timestamp", "audit_logs", ["company_id", "timestamp"])
    op.add_column("fleet_dispatch_records", sa.Column("downtime_hours", sa.Numeric(10,2)))
    op.add_column("fleet_dispatch_records", sa.Column("downtime_reason", sa.Text()))

def downgrade():
    op.drop_column("fleet_dispatch_records", "downtime_reason")
    op.drop_column("fleet_dispatch_records", "downtime_hours")
    op.drop_table("audit_logs")
