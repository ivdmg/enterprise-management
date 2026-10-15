"""Initial database schema migration matching PostgreSQL 16 DDL

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-10-11 20:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Enable UUID Extension
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')

    # 2. Create Custom ENUM Types
    user_role_enum = postgresql.ENUM("admin", "manager", "viewer", name="user_role_enum", create_type=False)
    file_status_enum = postgresql.ENUM("uploaded", "profiling", "awaiting_confirmation", "processed", "failed", name="file_status_enum", create_type=False)
    domain_category_enum = postgresql.ENUM("production_tenders", "cashflow_debt", "payroll_hr", "operational_tasks", name="domain_category_enum", create_type=False)
    project_risk_enum = postgresql.ENUM("normal", "warning", "critical", name="project_risk_enum", create_type=False)
    cashflow_direction_enum = postgresql.ENUM("incoming", "outgoing", name="cashflow_direction_enum", create_type=False)
    payroll_status_enum = postgresql.ENUM("accrued", "partially_paid", "paid", "overdue", name="payroll_status_enum", create_type=False)
    task_priority_enum = postgresql.ENUM("low", "medium", "high", "urgent", name="task_priority_enum", create_type=False)
    task_status_enum = postgresql.ENUM("pending", "in_progress", "completed", "overdue", name="task_status_enum", create_type=False)
    alert_severity_enum = postgresql.ENUM("CRITICAL", "WARNING", "INFO", name="alert_severity_enum", create_type=False)
    notification_channel_enum = postgresql.ENUM("IN_APP", "TELEGRAM", "EMAIL", name="notification_channel_enum", create_type=False)
    notification_status_enum = postgresql.ENUM("PENDING", "SENT", "FAILED", name="notification_status_enum", create_type=False)

    for enum_type in [
        user_role_enum,
        file_status_enum,
        domain_category_enum,
        project_risk_enum,
        cashflow_direction_enum,
        payroll_status_enum,
        task_priority_enum,
        task_status_enum,
        alert_severity_enum,
        notification_channel_enum,
        notification_status_enum,
    ]:
        enum_type.create(op.get_bind(), checkfirst=True)

    # 3. Create Trigger Function for updated_at
    op.execute(
        """
        CREATE OR REPLACE FUNCTION trigger_set_timestamp()
        RETURNS TRIGGER AS $$
        BEGIN
          NEW.updated_at = NOW();
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    # 4. Table: companies
    op.create_table(
        "companies",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuid_generate_v4()"), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("inn", sa.String(12), nullable=True),
        sa.Column("kpp", sa.String(9), nullable=True),
        sa.Column("timezone", sa.String(50), server_default="Europe/Moscow", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.execute(
        """
        CREATE TRIGGER set_timestamp_companies
        BEFORE UPDATE ON companies
        FOR EACH ROW EXECUTE PROCEDURE trigger_set_timestamp();
        """
    )

    # 5. Table: users
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuid_generate_v4()"), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("role", user_role_enum, server_default="viewer", nullable=False),
        sa.Column("telegram_chat_id", sa.BigInteger(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("idx_users_company", "users", ["company_id"])
    op.create_index("idx_users_telegram", "users", ["telegram_chat_id"], postgresql_where=sa.text("telegram_chat_id IS NOT NULL"))
    op.execute(
        """
        CREATE TRIGGER set_timestamp_users
        BEFORE UPDATE ON users
        FOR EACH ROW EXECUTE PROCEDURE trigger_set_timestamp();
        """
    )

    # 6. Table: uploaded_files
    op.create_table(
        "uploaded_files",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuid_generate_v4()"), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("uploaded_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("original_name", sa.String(255), nullable=False),
        sa.Column("storage_path", sa.String(500), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("sha256_hash", sa.String(64), nullable=False),
        sa.Column("status", file_status_enum, server_default="uploaded", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_uploaded_files_company_hash", "uploaded_files", ["company_id", "sha256_hash"])
    op.create_index("idx_uploaded_files_status", "uploaded_files", ["company_id", "status"])
    op.execute(
        """
        CREATE TRIGGER set_timestamp_uploaded_files
        BEFORE UPDATE ON uploaded_files
        FOR EACH ROW EXECUTE PROCEDURE trigger_set_timestamp();
        """
    )

    # 7. Table: file_templates
    op.create_table(
        "file_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuid_generate_v4()"), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("template_name", sa.String(255), nullable=False),
        sa.Column("sheet_name", sa.String(255), server_default="Sheet1", nullable=False),
        sa.Column("headers_fingerprint", sa.String(64), nullable=False),
        sa.Column("domain_category", domain_category_enum, nullable=False),
        sa.Column("column_mapping", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("confidence_score", sa.Numeric(5, 2), server_default="1.00", nullable=False),
        sa.Column("match_count", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("company_id", "headers_fingerprint", name="uq_company_fingerprint"),
    )
    op.create_index("idx_templates_lookup", "file_templates", ["company_id", "headers_fingerprint"])
    op.create_index("idx_templates_mapping_gin", "file_templates", ["column_mapping"], postgresql_using="gin")
    op.execute(
        """
        CREATE TRIGGER set_timestamp_file_templates
        BEFORE UPDATE ON file_templates
        FOR EACH ROW EXECUTE PROCEDURE trigger_set_timestamp();
        """
    )

    # 8. Table: parsing_jobs
    op.create_table(
        "parsing_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuid_generate_v4()"), primary_key=True),
        sa.Column("file_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("uploaded_files.id", ondelete="CASCADE"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(30), server_default="in_progress", nullable=False),
        sa.Column("confidence_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("ai_model_used", sa.String(50), nullable=True),
        sa.Column("extracted_rows_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("detected_headers", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("execution_time_ms", sa.Integer(), nullable=True),
        sa.Column("error_log", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_parsing_jobs_file", "parsing_jobs", ["file_id"])

    # 9. Table: tender_projects
    op.create_table(
        "tender_projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuid_generate_v4()"), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("uploaded_files.id", ondelete="SET NULL"), nullable=True),
        sa.Column("project_code", sa.String(100), nullable=True),
        sa.Column("project_name", sa.String(500), nullable=False),
        sa.Column("customer_name", sa.String(255), nullable=True),
        sa.Column("curator_name", sa.String(255), nullable=True),
        sa.Column("contract_sum", sa.Numeric(15, 2), server_default="0.00", nullable=False),
        sa.Column("completed_sum", sa.Numeric(15, 2), server_default="0.00", nullable=False),
        sa.Column("paid_sum", sa.Numeric(15, 2), server_default="0.00", nullable=False),
        sa.Column("debt_sum", sa.Numeric(15, 2), server_default="0.00", nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("deadline_date", sa.Date(), nullable=True),
        sa.Column("actual_completion_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(50), server_default="in_progress", nullable=False),
        sa.Column("risk_level", project_risk_enum, server_default="normal", nullable=False),
        sa.Column("penalty_amount_calculated", sa.Numeric(15, 2), server_default="0.00", nullable=False),
        sa.Column("custom_attributes", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_tender_company_status", "tender_projects", ["company_id", "status", "deadline_date"], postgresql_where=sa.text("deleted_at IS NULL"))
    op.create_index("idx_tender_risk", "tender_projects", ["company_id", "risk_level"], postgresql_where=sa.text("risk_level != 'normal'"))
    op.execute(
        """
        CREATE TRIGGER set_timestamp_tender_projects
        BEFORE UPDATE ON tender_projects
        FOR EACH ROW EXECUTE PROCEDURE trigger_set_timestamp();
        """
    )

    # 10. Table: cashflow_operations
    op.create_table(
        "cashflow_operations",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuid_generate_v4()"), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("uploaded_files.id", ondelete="SET NULL"), nullable=True),
        sa.Column("operation_date", sa.Date(), nullable=False),
        sa.Column("counterparty", sa.String(255), nullable=True),
        sa.Column("direction", cashflow_direction_enum, nullable=False),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("planned_amount", sa.Numeric(15, 2), server_default="0.00", nullable=False),
        sa.Column("actual_amount", sa.Numeric(15, 2), server_default="0.00", nullable=False),
        sa.Column("is_paid", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("account_name", sa.String(100), nullable=True),
        sa.Column("payment_due_date", sa.Date(), nullable=True),
        sa.Column("document_number", sa.String(100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_cashflow_company_date", "cashflow_operations", ["company_id", "operation_date", "direction"], postgresql_where=sa.text("deleted_at IS NULL"))
    op.create_index("idx_cashflow_due_unpaid", "cashflow_operations", ["company_id", "payment_due_date"], postgresql_where=sa.text("is_paid = false"))
    op.execute(
        """
        CREATE TRIGGER set_timestamp_cashflow_operations
        BEFORE UPDATE ON cashflow_operations
        FOR EACH ROW EXECUTE PROCEDURE trigger_set_timestamp();
        """
    )

    # 11. Table: payroll_records
    op.create_table(
        "payroll_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuid_generate_v4()"), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("uploaded_files.id", ondelete="SET NULL"), nullable=True),
        sa.Column("payroll_period", sa.String(20), nullable=False),
        sa.Column("employee_name", sa.String(255), nullable=False),
        sa.Column("department", sa.String(150), nullable=True),
        sa.Column("role_title", sa.String(150), nullable=True),
        sa.Column("accrued_amount", sa.Numeric(15, 2), server_default="0.00", nullable=False),
        sa.Column("paid_amount", sa.Numeric(15, 2), server_default="0.00", nullable=False),
        sa.Column("debt_amount", sa.Numeric(15, 2), server_default="0.00", nullable=False),
        sa.Column("payment_due_date", sa.Date(), nullable=True),
        sa.Column("status", payroll_status_enum, server_default="accrued", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_payroll_company_period", "payroll_records", ["company_id", "payroll_period"], postgresql_where=sa.text("deleted_at IS NULL"))
    op.create_index("idx_payroll_debt", "payroll_records", ["company_id", "status"], postgresql_where=sa.text("status = 'overdue'"))
    op.execute(
        """
        CREATE TRIGGER set_timestamp_payroll_records
        BEFORE UPDATE ON payroll_records
        FOR EACH ROW EXECUTE PROCEDURE trigger_set_timestamp();
        """
    )

    # 12. Table: operational_tasks
    op.create_table(
        "operational_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuid_generate_v4()"), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("uploaded_files.id", ondelete="SET NULL"), nullable=True),
        sa.Column("task_title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("responsible_person", sa.String(255), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("status", task_status_enum, server_default="pending", nullable=False),
        sa.Column("priority", task_priority_enum, server_default="medium", nullable=False),
        sa.Column("penalty_risk_desc", sa.Text(), nullable=True),
        sa.Column("estimated_penalty_amount", sa.Numeric(15, 2), server_default="0.00", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_tasks_company_due", "operational_tasks", ["company_id", "due_date", "status"], postgresql_where=sa.text("deleted_at IS NULL"))
    op.execute(
        """
        CREATE TRIGGER set_timestamp_operational_tasks
        BEFORE UPDATE ON operational_tasks
        FOR EACH ROW EXECUTE PROCEDURE trigger_set_timestamp();
        """
    )

    # 13. Table: system_alerts
    op.create_table(
        "system_alerts",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuid_generate_v4()"), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("domain_category", domain_category_enum, nullable=False),
        sa.Column("severity", alert_severity_enum, nullable=False),
        sa.Column("alert_type", sa.String(50), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=True),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("calculated_financial_impact", sa.Numeric(15, 2), server_default="0.00", nullable=False),
        sa.Column("trigger_date", sa.Date(), server_default=sa.func.current_date(), nullable=False),
        sa.Column("is_resolved", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("resolution_comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_alerts_company_unresolved", "system_alerts", ["company_id", "is_resolved", "severity"])
    op.create_index("idx_alerts_date", "system_alerts", ["company_id", sa.text("trigger_date DESC")])
    op.execute(
        """
        CREATE TRIGGER set_timestamp_system_alerts
        BEFORE UPDATE ON system_alerts
        FOR EACH ROW EXECUTE PROCEDURE trigger_set_timestamp();
        """
    )

    # 14. Table: notification_logs
    op.create_table(
        "notification_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuid_generate_v4()"), primary_key=True),
        sa.Column("alert_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("system_alerts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("channel", notification_channel_enum, nullable=False),
        sa.Column("recipient_target", sa.String(255), nullable=False),
        sa.Column("status", notification_status_enum, server_default="PENDING", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_notification_logs_alert", "notification_logs", ["alert_id"])

    # 15. Table: integration_settings
    op.create_table(
        "integration_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuid_generate_v4()"), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("telegram_bot_enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("telegram_bot_token", sa.String(255), nullable=True),
        sa.Column("telegram_channel_id", sa.BigInteger(), nullable=True),
        sa.Column("daily_digest_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("daily_digest_time", sa.String(5), server_default="08:30", nullable=False),
        sa.Column(
            "alert_rules",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text(
                '\'{"deadline_warning_days": 5, "cash_gap_forecast_days": 14, "notify_on_critical_instant": true}\'::jsonb'
            ),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.execute(
        """
        CREATE TRIGGER set_timestamp_integration_settings
        BEFORE UPDATE ON integration_settings
        FOR EACH ROW EXECUTE PROCEDURE trigger_set_timestamp();
        """
    )

    # 16. Seed Initial Demo Data (from schema.sql Section 7)
    op.execute(
        """
        INSERT INTO companies (id, name, inn, timezone)
        VALUES ('a0000000-0000-0000-0000-000000000001', 'ООО "ГлавСтройМонтаж"', '7701234567', 'Europe/Moscow')
        ON CONFLICT DO NOTHING;

        INSERT INTO users (id, company_id, email, password_hash, full_name, role)
        VALUES (
            'b0000000-0000-0000-0000-000000000001',
            'a0000000-0000-0000-0000-000000000001',
            'admin@glavstroy.ru',
            '$2b$12$qoXPodGKJwrVMGHkGaMueuDvg2urLfEEdmSRa8q9gX1bQCLFLh/lC',
            'Алексей Викторович (Генеральный)',
            'admin'
        )
        ON CONFLICT DO NOTHING;

        INSERT INTO integration_settings (company_id, telegram_bot_enabled, daily_digest_time)
        VALUES ('a0000000-0000-0000-0000-000000000001', false, '08:30')
        ON CONFLICT DO NOTHING;
        """
    )


def downgrade() -> None:
    # Drop tables in reverse order of foreign keys
    op.drop_table("integration_settings")
    op.drop_table("notification_logs")
    op.drop_table("system_alerts")
    op.drop_table("operational_tasks")
    op.drop_table("payroll_records")
    op.drop_table("cashflow_operations")
    op.drop_table("tender_projects")
    op.drop_table("parsing_jobs")
    op.drop_table("file_templates")
    op.drop_table("uploaded_files")
    op.drop_table("users")
    op.drop_table("companies")

    # Drop trigger function
    op.execute("DROP FUNCTION IF EXISTS trigger_set_timestamp CASCADE;")

    # Drop enums
    enums_to_drop = [
        "notification_status_enum",
        "notification_channel_enum",
        "alert_severity_enum",
        "task_status_enum",
        "task_priority_enum",
        "payroll_status_enum",
        "cashflow_direction_enum",
        "project_risk_enum",
        "domain_category_enum",
        "file_status_enum",
        "user_role_enum",
    ]
    for enum_name in enums_to_drop:
        op.execute(f"DROP TYPE IF EXISTS {enum_name} CASCADE;")
