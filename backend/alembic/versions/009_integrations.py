"""Tenant integration registry and durable import jobs."""

from alembic import op

revision = "009_integrations"
down_revision = "008_company_config"


def upgrade():
    tables = """
        CREATE TABLE public.company_integrations (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          company_id uuid NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
          provider varchar(24) NOT NULL CHECK (provider IN ('google_drive', 'test_workbook')),
          label varchar(160) NOT NULL,
          module_id varchar(64) NOT NULL,
          adapter_id varchar(64) NOT NULL,
          adapter_version varchar(32) NOT NULL,
          source_ref varchar(255) NOT NULL,
          secret_ref varchar(128),
          enabled boolean NOT NULL DEFAULT true,
          schedule_seconds integer CHECK (schedule_seconds BETWEEN 60 AND 86400),
          stale_after_seconds integer NOT NULL CHECK (stale_after_seconds BETWEEN 60 AND 604800),
          version integer NOT NULL DEFAULT 1,
          next_due_at timestamptz NOT NULL DEFAULT clock_timestamp(),
          last_attempt_at timestamptz,
          last_success_at timestamptz,
          last_success_version integer,
          last_fingerprint varchar(64),
          last_error_code varchar(64),
          published_file_id uuid,
          UNIQUE (company_id, id),
          UNIQUE (company_id, provider, source_ref),
          UNIQUE (company_id, published_file_id),
          FOREIGN KEY (company_id, published_file_id)
            REFERENCES public.uploaded_files(company_id, id) ON DELETE SET NULL (published_file_id),
          CHECK ((provider = 'google_drive' AND secret_ref IS NOT NULL)
                 OR (provider = 'test_workbook' AND secret_ref IS NULL))
        );

        CREATE TABLE public.integration_runs (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          company_id uuid NOT NULL,
          integration_id uuid NOT NULL,
          integration_version integer NOT NULL,
          config_revision integer NOT NULL DEFAULT 0,
          adapter_version varchar(32) NOT NULL,
          release_version varchar(64) NOT NULL,
          request_id varchar(64) NOT NULL,
          mode varchar(12) NOT NULL CHECK (mode IN ('preview', 'import')),
          state varchar(16) NOT NULL DEFAULT 'queued'
              CHECK (state IN ('queued','running','retry_wait','succeeded','failed','canceled')),
          idempotency_key varchar(128) NOT NULL,
          reason varchar(256) NOT NULL,
          approved_preview_id uuid,
          created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
          available_at timestamptz NOT NULL DEFAULT clock_timestamp(),
          started_at timestamptz,
          finished_at timestamptz,
          attempt_count integer NOT NULL DEFAULT 0,
          lease_generation integer NOT NULL DEFAULT 0,
          lease_until timestamptz,
          rows_processed integer,
          warning_count integer,
          error_code varchar(64),
          fingerprint varchar(64),
          approved_until timestamptz,
          UNIQUE (company_id, integration_id, id),
          UNIQUE (company_id, integration_id, idempotency_key),
          FOREIGN KEY (company_id, integration_id)
            REFERENCES public.company_integrations(company_id, id) ON DELETE CASCADE,
          FOREIGN KEY (company_id, integration_id, approved_preview_id)
            REFERENCES public.integration_runs(company_id, integration_id, id)
        );
        CREATE UNIQUE INDEX uq_integration_active_run
          ON public.integration_runs (company_id, integration_id)
          WHERE state IN ('queued','running','retry_wait');
        CREATE INDEX ix_integration_run_claim
          ON public.integration_runs (available_at, created_at)
          WHERE state IN ('queued','running','retry_wait');

        CREATE TABLE public.integration_worker_heartbeats (
          worker_id uuid PRIMARY KEY,
          seen_at timestamptz NOT NULL
        );

        CREATE TABLE public.integration_retry_requests (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          company_id uuid NOT NULL,
          integration_id uuid NOT NULL,
          requested_by uuid NOT NULL,
          reason varchar(256) NOT NULL,
          state varchar(16) NOT NULL DEFAULT 'pending',
          created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
          FOREIGN KEY (company_id, integration_id)
            REFERENCES public.company_integrations(company_id, id) ON DELETE CASCADE,
          FOREIGN KEY (company_id, requested_by) REFERENCES public.users(company_id, id)
        );
        CREATE UNIQUE INDEX uq_integration_retry_pending
          ON public.integration_retry_requests (company_id, integration_id) WHERE state = 'pending';
    """
    for statement in tables.strip().rstrip(";").split(";"):
        op.execute(statement)
    for table in ("company_integrations", "integration_runs", "integration_retry_requests"):
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY tenant_isolation ON public.{table}
            USING (company_id = NULLIF(current_setting('app.company_id', true), '')::uuid)
            WITH CHECK (company_id = NULLIF(current_setting('app.company_id', true), '')::uuid)
        """)
    op.execute("""
        CREATE FUNCTION public.schedule_integration_jobs(build_version text)
        RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path TO pg_catalog, pg_temp
        AS $$
        BEGIN
          PERFORM pg_advisory_xact_lock(580426722);
          WITH eligible_companies AS MATERIALIZED (
            SELECT c.id FROM public.companies AS c
            WHERE c.is_active AND EXISTS (
              SELECT FROM public.company_integrations AS i
              WHERE i.company_id = c.id AND i.enabled AND i.schedule_seconds IS NOT NULL
                AND i.last_success_version = i.version AND i.next_due_at <= clock_timestamp()
            )
            ORDER BY c.id FOR SHARE
          ), due AS (
            UPDATE public.company_integrations AS i
            SET next_due_at = clock_timestamp() + make_interval(secs => i.schedule_seconds)
            FROM eligible_companies AS c
            WHERE c.id = i.company_id
              AND i.enabled AND i.schedule_seconds IS NOT NULL
              AND i.last_success_version = i.version AND i.next_due_at <= clock_timestamp()
              AND NOT EXISTS (
                SELECT FROM public.company_config_revisions AS cfg
                WHERE cfg.company_id = i.company_id AND cfg.state = 'active'
                  AND NOT (
                    cfg.modules @> jsonb_build_array(jsonb_build_object('id','sources','enabled',true))
                    AND cfg.modules @> jsonb_build_array(jsonb_build_object('id',i.module_id,'enabled',true))
                  )
              )
              AND NOT EXISTS (
                SELECT FROM public.integration_runs AS r
                WHERE r.company_id = i.company_id AND r.integration_id = i.id
                  AND r.state IN ('queued','running','retry_wait')
              )
            RETURNING i.*
          )
          INSERT INTO public.integration_runs
            (company_id,integration_id,integration_version,config_revision,adapter_version,release_version,request_id,mode,idempotency_key,reason)
          SELECT company_id,id,version,coalesce((
                    SELECT cfg.revision FROM public.company_config_revisions AS cfg
                    WHERE cfg.company_id = due.company_id AND cfg.state = 'active'
                 ),0),adapter_version,left(build_version,64),gen_random_uuid()::text,
                 'import','schedule:' || next_due_at::text,'schedule'
          FROM due ON CONFLICT DO NOTHING;
        END
        $$
    """)
    op.execute("""
        CREATE FUNCTION public.claim_integration_job(p_worker_id uuid)
        RETURNS TABLE (run_id uuid, tenant_id uuid, generation integer)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path TO pg_catalog, pg_temp
        AS $$
        BEGIN
          PERFORM pg_advisory_xact_lock(580426721);
          INSERT INTO public.integration_worker_heartbeats (worker_id, seen_at)
            VALUES (p_worker_id, clock_timestamp())
            ON CONFLICT (worker_id) DO UPDATE SET seen_at = EXCLUDED.seen_at;

          UPDATE public.integration_runs AS r
            SET state = 'failed', finished_at = clock_timestamp(), lease_until = NULL, error_code = 'WORKER_LEASE_EXPIRED'
            WHERE r.id IN (
              SELECT expired.id FROM public.integration_runs AS expired
              WHERE expired.state = 'running' AND expired.lease_until <= clock_timestamp()
                AND expired.attempt_count >= 3 FOR UPDATE SKIP LOCKED
            );
          IF (SELECT count(*) FROM public.integration_runs AS r
              WHERE r.state = 'running' AND r.lease_until > clock_timestamp()) >= 2 THEN
            RETURN;
          END IF;

          RETURN QUERY
            WITH candidate AS (
              SELECT r.id FROM public.integration_runs AS r
              WHERE ((r.state IN ('queued','retry_wait') AND r.available_at <= clock_timestamp())
                     OR (r.state = 'running' AND r.lease_until <= clock_timestamp()))
                AND r.attempt_count < 3
                AND NOT EXISTS (
                  SELECT FROM public.integration_runs AS active
                  WHERE active.company_id = r.company_id AND active.state = 'running'
                    AND active.lease_until > clock_timestamp()
                )
              ORDER BY r.available_at, r.created_at, r.id
              FOR UPDATE SKIP LOCKED LIMIT 1
            )
            UPDATE public.integration_runs AS r
            SET state = 'running', attempt_count = r.attempt_count + 1,
                lease_generation = r.lease_generation + 1,
                lease_until = clock_timestamp() + interval '120 seconds',
                started_at = clock_timestamp()
            FROM candidate WHERE r.id = candidate.id
            RETURNING r.id, r.company_id, r.lease_generation;
        END
        $$
    """)
    op.execute("REVOKE ALL ON FUNCTION public.schedule_integration_jobs(text) FROM PUBLIC")
    op.execute("REVOKE ALL ON FUNCTION public.claim_integration_job(uuid) FROM PUBLIC")


def downgrade():
    op.execute("DROP FUNCTION public.claim_integration_job(uuid)")
    op.execute("DROP FUNCTION public.schedule_integration_jobs(text)")
    for table in ("integration_retry_requests", "integration_worker_heartbeats", "integration_runs", "company_integrations"):
        op.drop_table(table, schema="public")
