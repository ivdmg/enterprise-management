"""Store the latest engineer document register per company."""

import sqlalchemy as sa
from alembic import op

revision = "005_engineer_documents"
down_revision = "004_audit_dispatch"


def upgrade():
    op.add_column("companies", sa.Column("engineer_documents", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("companies", "engineer_documents")
