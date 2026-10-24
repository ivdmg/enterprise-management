"""Track editable Drive source documents per company."""
from alembic import op
import sqlalchemy as sa

revision = "003_drive_sources"
down_revision = "d2371ad1f734"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("uploaded_files", sa.Column("google_drive_id", sa.String(255), nullable=True))
    op.add_column("uploaded_files", sa.Column("google_drive_link", sa.String(1000), nullable=True))
    op.create_unique_constraint("uq_company_drive_file", "uploaded_files", ["company_id", "google_drive_id"])

def downgrade():
    op.drop_constraint("uq_company_drive_file", "uploaded_files", type_="unique")
    op.drop_column("uploaded_files", "google_drive_link")
    op.drop_column("uploaded_files", "google_drive_id")
