"""Closed, tenant-aware authentication storage."""

from alembic import op
import sqlalchemy as sa

revision = "007_platform_auth"
down_revision = "006_tenant_isolation"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("companies", sa.Column("code", sa.String(63)))
    op.execute("UPDATE companies SET code = 'company-' || id::text")
    op.alter_column("companies", "code", nullable=False, server_default=sa.text("'company-' || gen_random_uuid()::text"))
    op.create_unique_constraint("uq_companies_code", "companies", ["code"])
    op.add_column("users", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
    op.drop_constraint("uq_users_email", "users", type_="unique")
    op.execute("UPDATE users SET email = lower(trim(email))")
    op.create_unique_constraint("uq_users_company_email", "users", ["company_id", "email"])
    statements = """
        CREATE TABLE platform_operators (
          id uuid PRIMARY KEY, email varchar(255) UNIQUE NOT NULL,
          full_name varchar(255) NOT NULL, password_hash varchar(255) NOT NULL,
          role varchar(16) NOT NULL CHECK (role IN ('owner','support')), is_active boolean NOT NULL
        );
        CREATE TABLE auth_grants (
          token_hash varchar(64) PRIMARY KEY, purpose varchar(32) NOT NULL,
          company_id uuid REFERENCES companies(id) ON DELETE CASCADE,
          subject_id uuid NOT NULL, expires_at timestamptz NOT NULL, payload jsonb NOT NULL DEFAULT '{}',
          family uuid, consumed_at timestamptz, revoked_at timestamptz
        );
        CREATE INDEX auth_grants_subject ON auth_grants (company_id, subject_id, purpose);
        CREATE INDEX auth_grants_family ON auth_grants (family);
        CREATE TABLE auth_factors (
          subject_id uuid PRIMARY KEY, secret_ciphertext text NOT NULL, last_counter bigint NOT NULL
        );
        CREATE TABLE auth_recovery_codes (
          subject_id uuid NOT NULL REFERENCES auth_factors(subject_id) ON DELETE CASCADE,
          code_hash varchar(64) NOT NULL, PRIMARY KEY(subject_id, code_hash)
        );
        CREATE TABLE auth_rate_limits (
          bucket varchar(64) PRIMARY KEY, expires_at timestamptz NOT NULL, count integer NOT NULL
        );
        CREATE TABLE company_access_requests (
          id uuid PRIMARY KEY, company_id uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
          email varchar(255) NOT NULL, full_name varchar(255) NOT NULL,
          role varchar(16) NOT NULL CHECK (role IN ('manager','viewer')),
          reason text, state varchar(20) NOT NULL DEFAULT 'pending',
          created_at timestamptz NOT NULL DEFAULT now()
        );
        ALTER TABLE company_access_requests ENABLE ROW LEVEL SECURITY;
        CREATE POLICY tenant_company_access_requests ON company_access_requests
          USING (company_id = nullif(current_setting('app.company_id', true), '')::uuid)
          WITH CHECK (company_id = nullif(current_setting('app.company_id', true), '')::uuid);
        CREATE FUNCTION public.auth_tenant_subject(company_code text, email_address text)
          RETURNS TABLE (company_id uuid, user_id uuid)
          LANGUAGE sql SECURITY DEFINER SET search_path TO pg_catalog, pg_temp
          AS $$
            SELECT c.id, u.id FROM public.companies AS c
              JOIN public.users AS u ON u.company_id = c.id
              WHERE c.code = company_code AND u.email = email_address
          $$;
        REVOKE ALL ON FUNCTION public.auth_tenant_subject(text, text) FROM PUBLIC;
    """
    for statement in statements.strip().split(";\n"):
        op.execute(statement.strip().rstrip(";"))


def downgrade():
    op.execute("DROP FUNCTION public.auth_tenant_subject(text, text)")
    for table in ("company_access_requests", "auth_rate_limits", "auth_recovery_codes", "auth_factors", "auth_grants", "platform_operators"):
        op.drop_table(table)
    op.create_unique_constraint("uq_users_email", "users", ["email"])
    op.drop_constraint("uq_users_company_email", "users", type_="unique")
    op.drop_column("users", "version")
    op.drop_constraint("uq_companies_code", "companies", type_="unique")
    op.drop_column("companies", "code")
