export type IntegrationState =
  | 'unchecked'
  | 'running'
  | 'current'
  | 'stale'
  | 'needs_attention'
  | 'paused';

export interface IntegrationStatus {
  id: string;
  label: string;
  type: string;
  module_id: string;
  adapter_id: string;
  adapter_version: string;
  status: IntegrationState;
  last_success_at: string | null;
  last_attempt_at: string | null;
  next_attempt_at: string | null;
  stale_after_seconds: number;
  version: number;
  error?: {
    code: string;
    message: string;
    next_step: string;
    request_id: string | null;
  } | null;
}

export type IncidentState = 'new' | 'in_progress' | 'escalated' | 'verifying' | 'closed';

export interface IncidentSummary {
  id: string;
  integration_id: string | null;
  severity: string;
  state: IncidentState;
  code: string;
  message: string;
  impact: string;
  next_step: string;
  run_id: string | null;
  assignee_id: string | null;
  version: number;
  opened_at: string;
  updated_at: string;
}
