"""Restricted platform company lifecycle and invitation controls."""

from alembic import op

revision = "011_platform_admin"
down_revision = "010_operations"


def upgrade():
    statements = """
        ALTER TABLE public.companies ADD COLUMN platform_state varchar(12) NOT NULL DEFAULT 'active'
          CHECK (platform_state IN ('draft','active','paused','closed'));
        UPDATE public.companies SET platform_state='paused' WHERE NOT is_active;
        ALTER TABLE public.companies ADD COLUMN platform_version integer NOT NULL DEFAULT 1;
        ALTER TABLE public.company_access_requests ADD COLUMN version integer NOT NULL DEFAULT 1;
        ALTER TABLE public.company_access_requests ADD COLUMN decision_reason text;
        CREATE TABLE public.company_invitations (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          company_id uuid NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
          user_id uuid NOT NULL,
          access_request_id uuid REFERENCES public.company_access_requests(id),
          email varchar(255) NOT NULL,
          role varchar(16) NOT NULL,
          state varchar(16) NOT NULL DEFAULT 'pending' CHECK (state IN ('pending','accepted','revoked')),
          created_at timestamptz NOT NULL DEFAULT now(),
          expires_at timestamptz NOT NULL,
          delivery_state varchar(12) NOT NULL DEFAULT 'pending' CHECK (delivery_state IN ('pending','sent','failed','canceled')),
          version integer NOT NULL DEFAULT 1,
          FOREIGN KEY (company_id,user_id) REFERENCES public.users(company_id,id)
        );
        CREATE UNIQUE INDEX uq_company_pending_invitation ON public.company_invitations(company_id,user_id)
          WHERE state='pending';
        ALTER TABLE public.company_invitations ENABLE ROW LEVEL SECURITY;
        CREATE POLICY tenant_company_invitations ON public.company_invitations
          USING (company_id=nullif(current_setting('app.company_id',true),'')::uuid)
          WITH CHECK (company_id=nullif(current_setting('app.company_id',true),'')::uuid);
        CREATE TABLE public.invitation_outbox (
          invitation_id uuid PRIMARY KEY REFERENCES public.company_invitations(id) ON DELETE CASCADE,
          company_id uuid NOT NULL,
          invitation_version integer NOT NULL,
          token_ciphertext text NOT NULL,
          attempt_count integer NOT NULL DEFAULT 0,
          available_at timestamptz NOT NULL DEFAULT now()
        );
    """
    for statement in statements.strip().split(";\n"):
        op.execute(statement.strip().rstrip(";"))

    functions = {
        "platform_company_summary(uuid)": """
            CREATE FUNCTION public.platform_company_summary(target uuid)
            RETURNS TABLE (id uuid,code text,name text,state text,version integer,modules jsonb,
                           integration_count bigint,last_success_at timestamptz,open_incident_count bigint,health text)
            LANGUAGE sql SECURITY DEFINER SET search_path TO pg_catalog, pg_temp
            AS $$
              SELECT c.id,c.code::text,c.name::text,c.platform_state::text,c.platform_version,r.modules,
                     i.count,i.last_success_at,n.count,
                     CASE WHEN n.count > 0 OR i.unhealthy THEN 'degraded'
                          WHEN i.last_success_at IS NULL THEN 'unknown' ELSE 'healthy' END
              FROM public.companies AS c
              LEFT JOIN public.company_config_revisions AS r ON r.company_id=c.id AND r.state='active'
              CROSS JOIN LATERAL (
                SELECT count(*) AS count,max(q.last_success_at) AS last_success_at,
                  COALESCE(bool_or(q.enabled AND (q.last_error_code IS NOT NULL OR
                    q.last_success_at < clock_timestamp()-make_interval(secs=>q.stale_after_seconds))),false) AS unhealthy
                FROM public.company_integrations AS q WHERE q.company_id=c.id
              ) AS i
              CROSS JOIN LATERAL (
                SELECT count(*) AS count FROM public.platform_incidents AS j WHERE j.company_id=c.id AND j.state<>'closed'
              ) AS n
              WHERE target IS NULL OR c.id=target
            $$
        """,
        "platform_company_lock(uuid)": """
            CREATE FUNCTION public.platform_company_lock(target uuid)
            RETURNS TABLE (state text,version integer,code text)
            LANGUAGE sql SECURITY DEFINER SET search_path TO pg_catalog, pg_temp
            AS $$
              SELECT c.platform_state::text,c.platform_version,c.code::text
              FROM public.companies AS c WHERE c.id=target FOR UPDATE
            $$
        """,
        "platform_company_create(uuid,text,text)": """
            CREATE FUNCTION public.platform_company_create(company_id uuid, company_code text, company_name text)
            RETURNS uuid LANGUAGE sql SECURITY DEFINER SET search_path TO pg_catalog, pg_temp
            AS $$
              INSERT INTO public.companies (id,code,name,platform_state,is_active,timezone)
              VALUES (company_id,company_code,company_name,'draft',false,'Europe/Moscow')
              ON CONFLICT DO NOTHING RETURNING id
            $$
        """,
        "platform_company_transition(uuid,integer,text)": """
            CREATE FUNCTION public.platform_company_transition(target uuid, expected integer, next_state text)
            RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path TO pg_catalog, pg_temp
            AS $$
            DECLARE previous text;
            DECLARE current_version integer;
            BEGIN
              SELECT c.platform_state,c.platform_version INTO previous,current_version
                FROM public.companies AS c WHERE c.id=target FOR UPDATE;
              IF NOT FOUND THEN RETURN 'NOT_FOUND'; END IF;
              IF current_version<>expected THEN RETURN 'STALE_REVISION'; END IF;
              IF NOT ((previous='draft' AND next_state='active')
                   OR (previous='active' AND next_state='paused')
                   OR (previous='paused' AND next_state IN ('active','closed'))) THEN
                RETURN 'CONFLICT';
              END IF;
              IF next_state='active' THEN
                IF NOT EXISTS (SELECT 1 FROM public.company_config_revisions WHERE company_id=target AND state='active')
                   OR NOT EXISTS (
                     SELECT 1 FROM public.users AS u WHERE u.company_id=target AND u.role='admin' AND (
                       u.is_active OR EXISTS (
                         SELECT 1 FROM public.company_invitations AS inv
                         WHERE inv.company_id=target AND inv.user_id=u.id AND inv.state='pending' AND inv.expires_at>now()
                       )
                     )
                   )
                   OR EXISTS (
                     SELECT 1 FROM public.company_integrations AS i WHERE i.company_id=target AND i.enabled
                       AND i.last_success_version IS DISTINCT FROM i.version AND NOT EXISTS (
                         SELECT 1 FROM public.integration_runs AS r
                         WHERE r.company_id=target AND r.integration_id=i.id AND r.mode='preview'
                           AND r.state='succeeded' AND r.integration_version=i.version AND r.approved_until>now()
                           AND r.config_revision=(SELECT revision FROM public.company_config_revisions
                             WHERE company_id=target AND state='active')
                       )
                   ) THEN RETURN 'COMPANY_NOT_READY'; END IF;
              ELSE
                UPDATE public.auth_grants SET revoked_at=now() WHERE company_id=target AND revoked_at IS NULL;
                UPDATE public.company_invitations SET state='revoked',delivery_state='canceled',version=version+1
                  WHERE company_id=target AND state='pending';
                UPDATE public.company_access_requests SET state='pending',version=version+1
                  WHERE company_id=target AND state='invited';
                DELETE FROM public.invitation_outbox WHERE company_id=target;
                UPDATE public.integration_runs SET state='canceled',lease_until=NULL,finished_at=clock_timestamp()
                  WHERE company_id=target AND state IN ('queued','running','retry_wait');
              END IF;
              UPDATE public.companies SET platform_state=next_state,is_active=(next_state='active'),
                platform_version=platform_version+1 WHERE id=target;
              RETURN 'OK';
            END
            $$
        """,
        "platform_transfer_director(uuid,integer,text,text)": """
            CREATE FUNCTION public.platform_transfer_director(
              target uuid, expected integer, current_address text, successor_address text)
            RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path TO pg_catalog, pg_temp
            AS $$
            DECLARE current_id uuid;
            DECLARE successor_id uuid;
            DECLARE current_version integer;
            BEGIN
              SELECT c.platform_version INTO current_version FROM public.companies AS c
                WHERE c.id=target AND c.platform_state='active' FOR UPDATE;
              IF NOT FOUND THEN RETURN 'CONFLICT'; END IF;
              IF current_version<>expected THEN RETURN 'STALE_REVISION'; END IF;
              SELECT id INTO current_id FROM public.users
                WHERE company_id=target AND email=current_address AND role='admin' AND is_active FOR UPDATE;
              SELECT id INTO successor_id FROM public.users
                WHERE company_id=target AND email=successor_address AND role='admin' AND is_active FOR UPDATE;
              IF current_id IS NULL OR successor_id IS NULL OR current_id=successor_id THEN
                RETURN 'LAST_DIRECTOR';
              END IF;
              UPDATE public.users SET is_active=false,version=version+1 WHERE company_id=target AND id=current_id;
              UPDATE public.auth_grants SET revoked_at=now()
                WHERE company_id=target AND subject_id=current_id AND revoked_at IS NULL;
              UPDATE public.companies SET platform_version=platform_version+1 WHERE id=target;
              RETURN 'OK';
            END
            $$
        """,
        "platform_prepare_invitee(uuid,text,text,text)": """
            CREATE FUNCTION public.platform_prepare_invitee(target uuid,address text,display_name text,tenant_role text)
            RETURNS TABLE (user_id uuid,user_version integer)
            LANGUAGE sql SECURITY DEFINER SET search_path TO pg_catalog, pg_temp
            AS $$
              INSERT INTO public.users (id,company_id,email,full_name,role,password_hash,is_active)
                VALUES (gen_random_uuid(),target,address,display_name,tenant_role::public.user_role_enum,'!invited',false)
              ON CONFLICT (company_id,email) DO UPDATE SET full_name=excluded.full_name
                WHERE users.password_hash='!invited' AND NOT users.is_active AND users.role=excluded.role
              RETURNING id,version
            $$
        """,
        "platform_pending_invitee(uuid,uuid)": """
            CREATE FUNCTION public.platform_pending_invitee(target uuid, subject uuid)
            RETURNS TABLE (user_id uuid,user_version integer)
            LANGUAGE sql SECURITY DEFINER SET search_path TO pg_catalog, pg_temp
            AS $$
              SELECT id,version FROM public.users WHERE company_id=target AND id=subject
                AND password_hash='!invited' AND NOT is_active FOR UPDATE
            $$
        """,
        "platform_pending_invitation_company()": """
            CREATE FUNCTION public.platform_pending_invitation_company()
            RETURNS uuid LANGUAGE sql SECURITY DEFINER SET search_path TO pg_catalog, pg_temp
            AS $$
              SELECT o.company_id FROM public.invitation_outbox AS o
              JOIN public.companies AS c ON c.id=o.company_id AND c.is_active
              WHERE o.available_at<=now() ORDER BY o.available_at,o.invitation_id LIMIT 1
            $$
        """,
        "platform_preview_is_approved(uuid,uuid,uuid,integer,integer)": """
            CREATE FUNCTION public.platform_preview_is_approved(
              target uuid, integration uuid, approval uuid, integration_revision integer, company_revision integer)
            RETURNS boolean LANGUAGE sql SECURITY DEFINER SET search_path TO pg_catalog, pg_temp
            AS $$
              SELECT EXISTS (
                SELECT 1 FROM public.integration_runs AS r
                WHERE r.company_id=target AND r.integration_id=integration AND r.id=approval
                  AND r.mode='preview' AND r.state='succeeded' AND r.approved_until>clock_timestamp()
                  AND r.integration_version=integration_revision AND r.config_revision=company_revision
                  AND r.fingerprint IS NOT NULL
              )
            $$
        """,
        "platform_approve_preview(uuid,uuid,integer,integer)": """
            CREATE FUNCTION public.platform_approve_preview(
              target uuid, run uuid, integration_revision integer, company_revision integer)
            RETURNS timestamptz LANGUAGE sql SECURITY DEFINER SET search_path TO pg_catalog, pg_temp
            AS $$
              UPDATE public.integration_runs AS r SET approved_until=clock_timestamp()+interval '24 hours'
              WHERE r.company_id=target AND r.id=run AND r.mode='preview' AND r.state='succeeded'
                AND r.integration_version=integration_revision AND r.config_revision=company_revision
                AND r.fingerprint IS NOT NULL
              RETURNING r.approved_until
            $$
        """,
    }
    for signature, statement in functions.items():
        op.execute(statement)
        op.execute(f"REVOKE ALL ON FUNCTION public.{signature} FROM PUBLIC")


def downgrade():
    for signature in (
        "platform_approve_preview(uuid,uuid,integer,integer)", "platform_preview_is_approved(uuid,uuid,uuid,integer,integer)",
        "platform_pending_invitation_company()", "platform_pending_invitee(uuid,uuid)",
        "platform_prepare_invitee(uuid,text,text,text)",
        "platform_transfer_director(uuid,integer,text,text)",
        "platform_company_transition(uuid,integer,text)", "platform_company_create(uuid,text,text)",
        "platform_company_lock(uuid)", "platform_company_summary(uuid)",
    ):
        op.execute(f"DROP FUNCTION public.{signature}")
    op.drop_table("invitation_outbox")
    op.drop_table("company_invitations")
    op.drop_column("company_access_requests", "decision_reason")
    op.drop_column("company_access_requests", "version")
    op.drop_column("companies", "platform_version")
    op.drop_column("companies", "platform_state")
