"""Safe operational events, incidents and audit of platform actions."""

from alembic import op

revision = "010_operations"
down_revision = "009_integrations"


def upgrade():
    statements = """
        CREATE TABLE public.platform_incidents (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id uuid NOT NULL,
            integration_id uuid NOT NULL,
            run_id uuid NOT NULL,
            code varchar(64) NOT NULL,
            severity varchar(16) NOT NULL CHECK (severity IN ('warning', 'error', 'critical')),
            state varchar(16) NOT NULL DEFAULT 'new'
                CHECK (state IN ('new', 'in_progress', 'escalated', 'verifying', 'closed')),
            assignee_id uuid REFERENCES public.platform_operators(id),
            version integer NOT NULL DEFAULT 1,
            opened_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            FOREIGN KEY (company_id, integration_id, run_id)
                REFERENCES public.integration_runs(company_id, integration_id, id) ON DELETE CASCADE
        );
        CREATE UNIQUE INDEX uq_platform_incidents_open_code
            ON public.platform_incidents (company_id, integration_id, code) WHERE state <> 'closed';
        CREATE INDEX ix_platform_incidents_company
            ON public.platform_incidents (company_id, updated_at DESC, id DESC);

        CREATE TABLE public.platform_integration_events (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id uuid NOT NULL,
            integration_id uuid NOT NULL,
            run_id uuid NOT NULL,
            code varchar(64) NOT NULL,
            severity varchar(16) NOT NULL CHECK (severity IN ('info', 'warning', 'error', 'critical')),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (company_id, integration_id, run_id, code),
            FOREIGN KEY (company_id, integration_id, run_id)
                REFERENCES public.integration_runs(company_id, integration_id, id) ON DELETE CASCADE
        );
        CREATE INDEX ix_platform_integration_events_company
            ON public.platform_integration_events (company_id, created_at DESC, id DESC);

        CREATE TABLE public.platform_operation_audit (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            actor_id uuid NOT NULL REFERENCES public.platform_operators(id),
            company_id uuid,
            action varchar(64) NOT NULL,
            entity_id uuid,
            result varchar(24) NOT NULL,
            correlation_id varchar(64),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp()
        );
        CREATE INDEX ix_platform_operation_audit_time
            ON public.platform_operation_audit (created_at DESC, id DESC);

        CREATE VIEW public.platform_run_correlation AS
            SELECT company_id, integration_id, id AS run_id, request_id
            FROM public.integration_runs
            WHERE company_id = NULLIF(current_setting('app.company_id', true), '')::uuid;

        CREATE FUNCTION public.platform_operation_status()
        RETURNS TABLE (worker_heartbeat_at timestamptz, queue_depth bigint, active_incident_count bigint)
        LANGUAGE sql SECURITY DEFINER SET search_path TO pg_catalog, pg_temp
        AS $$
            SELECT (SELECT max(seen_at) FROM public.integration_worker_heartbeats),
                   (SELECT count(*) FROM public.integration_runs WHERE state IN ('queued', 'retry_wait')),
                   (SELECT count(*) FROM public.platform_incidents WHERE state <> 'closed')
        $$;
        REVOKE ALL ON FUNCTION public.platform_operation_status() FROM PUBLIC;
    """
    for statement in statements.strip().split(";"):
        if statement.strip():
            op.execute(statement)
    for table in ("platform_incidents", "platform_integration_events"):
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY tenant_isolation ON public.{table}
            USING (company_id = NULLIF(current_setting('app.company_id', true), '')::uuid)
            WITH CHECK (company_id = NULLIF(current_setting('app.company_id', true), '')::uuid)
        """)


def downgrade():
    statements = """
        DROP FUNCTION public.platform_operation_status();
        DROP VIEW public.platform_run_correlation;
        DROP TABLE public.platform_operation_audit;
        DROP TABLE public.platform_integration_events;
        DROP TABLE public.platform_incidents;
    """
    for statement in statements.strip().split(";"):
        if statement.strip():
            op.execute(statement)
