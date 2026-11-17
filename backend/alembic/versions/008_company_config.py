"""Tenant module configuration and revision history."""

from alembic import op

revision = "008_company_config"
down_revision = "007_platform_auth"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE company_config_revisions (
          company_id uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
          revision integer NOT NULL CHECK (revision > 0),
          base_revision integer NOT NULL DEFAULT 0 CHECK (base_revision >= 0),
          state varchar(16) NOT NULL CHECK (state IN ('draft','active','archived')),
          modules jsonb NOT NULL,
          actor_id uuid,
          reason text,
          created_at timestamptz NOT NULL DEFAULT now(),
          PRIMARY KEY (company_id, revision)
        )
    """)
    op.execute("CREATE UNIQUE INDEX uq_company_config_active ON company_config_revisions(company_id) WHERE state='active'")
    op.execute("ALTER TABLE company_config_revisions ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_company_config ON company_config_revisions
          USING (company_id = nullif(current_setting('app.company_id', true), '')::uuid)
          WITH CHECK (company_id = nullif(current_setting('app.company_id', true), '')::uuid)
    """)
    op.execute("""
        CREATE TABLE company_config_requests (
          company_id uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
          actor_id uuid NOT NULL,
          action text NOT NULL,
          key_hash varchar(64) NOT NULL,
          request_hash varchar(64) NOT NULL,
          response jsonb NOT NULL,
          PRIMARY KEY (company_id, actor_id, action, key_hash)
        )
    """)
    op.execute("ALTER TABLE company_config_requests ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_company_config_requests ON company_config_requests
          USING (company_id = nullif(current_setting('app.company_id', true), '')::uuid)
          WITH CHECK (company_id = nullif(current_setting('app.company_id', true), '')::uuid)
    """)
    op.execute("""
        CREATE FUNCTION public.platform_company_exists(company uuid) RETURNS boolean
          LANGUAGE sql SECURITY DEFINER SET search_path TO pg_catalog, pg_temp
          AS $$ SELECT EXISTS(SELECT 1 FROM public.companies WHERE id=company) $$
    """)
    op.execute("REVOKE ALL ON FUNCTION public.platform_company_exists(uuid) FROM PUBLIC")


def downgrade():
    op.execute("DROP FUNCTION public.platform_company_exists(uuid)")
    op.drop_table("company_config_requests")
    op.drop_table("company_config_revisions")
