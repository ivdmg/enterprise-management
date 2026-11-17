"""Scope client data and protect references across tenant boundaries."""

from alembic import op
import sqlalchemy as sa

revision = "006_tenant_isolation"
down_revision = "005_engineer_documents"

TENANT_TABLES = (
    "companies", "users", "uploaded_files", "file_templates", "parsing_jobs",
    "tender_projects", "cashflow_operations", "payroll_records", "operational_tasks",
    "procurement_items", "fleet_dispatch_records", "system_alerts",
    "notification_logs", "integration_settings", "audit_logs",
)
INHERITED_TENANTS = (
    ("parsing_jobs", "file_id", "uploaded_files"),
    ("notification_logs", "alert_id", "system_alerts"),
)
REFERENCES = (
    *INHERITED_TENANTS,
    ("uploaded_files", "uploaded_by_user_id", "users"),
    ("system_alerts", "resolved_by_user_id", "users"),
    ("audit_logs", "user_id", "users"),
    *(
        (table, "file_id", "uploaded_files")
        for table in (
            "tender_projects", "cashflow_operations", "payroll_records",
            "operational_tasks", "procurement_items", "fleet_dispatch_records",
        )
    ),
)
PARENT_TABLES = ("users", "uploaded_files", "system_alerts")


def upgrade() -> None:
    for table, reference, parent in INHERITED_TENANTS:
        op.add_column(table, sa.Column("company_id", sa.Uuid(), nullable=True))
        op.execute(f"""
            UPDATE {table} AS child
            SET company_id = parent.company_id
            FROM {parent} AS parent
            WHERE parent.id = child.{reference}
        """)
        op.alter_column(table, "company_id", nullable=False)
        op.create_index(f"ix_{table}_company_id", table, ["company_id"])

    for table in PARENT_TABLES:
        op.create_unique_constraint(f"uq_{table}_company_id_id", table, ["company_id", "id"])
    for table, reference, parent in REFERENCES:
        # Keep the original FK's CASCADE/SET NULL semantics and ORM relationship.
        # The deferred composite check validates ownership after those triggers run.
        op.create_foreign_key(
            f"fk_{table}_{reference}_tenant", table, parent,
            ["company_id", reference], ["company_id", "id"],
            deferrable=True, initially="DEFERRED",
        )

    tenant = "NULLIF(current_setting('app.company_id', true), '')::uuid"
    for table in TENANT_TABLES:
        column = "id" if table == "companies" else "company_id"
        predicate = f"{column} = {tenant}"
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY tenant_isolation ON {table}
            USING ({predicate}) WITH CHECK ({predicate})
        """)


def downgrade() -> None:
    for table in reversed(TENANT_TABLES):
        op.execute(f"DROP POLICY tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    for table, reference, _ in reversed(REFERENCES):
        op.drop_constraint(f"fk_{table}_{reference}_tenant", table, type_="foreignkey")
    for table in reversed(PARENT_TABLES):
        op.drop_constraint(f"uq_{table}_company_id_id", table, type_="unique")
    for table, _, _ in reversed(INHERITED_TENANTS):
        op.drop_index(f"ix_{table}_company_id", table_name=table)
        op.drop_column(table, "company_id")
