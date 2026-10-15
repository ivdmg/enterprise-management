/* ============================
   TypeScript interfaces based on OpenAPI v1 contracts
   ============================ */

// --- Auth ---
export interface RegisterRequest {
  company_name: string;
  inn?: string;
  full_name: string;
  email: string;
  password: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface UserProfile {
  id: string;
  email: string;
  full_name: string;
  role: string;
  telegram_connected: boolean;
}

// --- API Envelope ---
export interface ApiResponse<T> {
  success: boolean;
  data: T;
  error: ApiError | null;
  meta?: ApiMeta;
}

export interface ApiError {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}

export interface ApiMeta {
  timestamp?: string;
  page?: number;
  limit?: number;
  total_items?: number;
  total_pages?: number;
  generated_at?: string;
}

// --- Files ---
export interface FileUploadData {
  file_id: string;
  original_name: string;
  file_size_bytes: number;
  sha256_hash?: string;
  status: string;
  sheets: string[];
  is_cached_template?: boolean;
}

export interface FileListItem {
  id: string;
  original_name: string;
  file_size_bytes: number;
  status: string;
  uploaded_by: string;
  created_at: string;
}

// --- Mapping ---
export interface ColumnMapping {
  source_column: string;
  sample_values: string[];
  target_field: string | null;
  confidence: number;
  is_required?: boolean;
}

export interface CanonicalField {
  field: string;
  label: string;
  required: boolean;
}

export interface MappingPreviewData {
  file_id: string;
  sheet_name: string;
  suggested_domain: string;
  confidence_score: number;
  source_type?: string;
  total_rows_detected?: number;
  columns_mapping: ColumnMapping[];
  available_canonical_fields: CanonicalField[];
}

export interface MappingConfirmRequest {
  sheet_name: string;
  domain_category: DomainCategory;
  template_name?: string;
  mappings: Record<string, string>;
}

export interface MappingConfirmData {
  file_id: string;
  status: string;
  imported_rows_count: number;
  alerts_triggered_count: number;
  template_saved?: boolean;
}

export type DomainCategory =
  | 'production_tenders'
  | 'cashflow_debt'
  | 'payroll_hr'
  | 'operational_tasks';

// --- Dashboard ---
export interface FinancialHealth {
  current_cash_balance: number;
  forecast_14d_inflow?: number;
  forecast_14d_outflow?: number;
  is_cash_gap_predicted: boolean;
  gap_deficit_amount?: number;
  gap_date?: string | null;
}

export interface ProductionHealth {
  total_active_projects: number;
  total_portfolio_sum?: number;
  average_completion_percent?: number;
  projects_at_risk_count: number;
  total_calculated_penalties: number;
}

export interface AlertsOverview {
  critical_count: number;
  warning_count: number;
  info_count?: number;
}

export interface FireItem {
  id: string;
  severity: 'CRITICAL' | 'WARNING' | 'INFO';
  title: string;
  description: string;
  financial_impact: number;
  due_date: string;
  responsible: string;
}

export interface DashboardSummary {
  financial_health: FinancialHealth;
  production_health: ProductionHealth;
  alerts_overview: AlertsOverview;
  top_fire_items: FireItem[];
}

// --- Finance ---
export interface CashDynamicsPoint {
  date: string;
  incoming: number;
  outgoing: number;
}

export interface DebtorCreditor {
  counterparty: string;
  debt_sum: number;
  overdue_days?: number;
  payment_due_date?: string;
}

export interface FinanceData {
  total_incoming: number;
  total_outgoing: number;
  net_cash_flow: number;
  dynamics: CashDynamicsPoint[];
  top_debtors: DebtorCreditor[];
  top_creditors: DebtorCreditor[];
}

// --- Projects ---
export interface Project {
  id: string;
  project_code?: string;
  project_name: string;
  customer_name?: string;
  curator_name?: string;
  contract_sum: number;
  completed_sum: number;
  paid_sum?: number;
  debt_sum?: number;
  completion_percent?: number;
  start_date?: string;
  deadline_date?: string;
  days_overdue: number;
  risk_level: 'critical' | 'warning' | 'normal';
  penalty_amount_calculated?: number;
}

// --- Alerts ---
export interface Alert {
  id: string;
  severity: 'CRITICAL' | 'WARNING' | 'INFO';
  title: string;
  description?: string;
  calculated_financial_impact: number;
  is_resolved: boolean;
  created_at?: string;
  resolved_at?: string;
  resolution_comment?: string;
}

// --- Payroll ---
export interface DepartmentPayroll {
  department: string;
  accrued: number;
  paid: number;
  debt: number;
}

export interface PayrollData {
  period: string;
  total_accrued: number;
  total_paid: number;
  total_debt: number;
  next_payment_deadline: string;
  by_department: DepartmentPayroll[];
}

// --- Integrations & Settings ---
export interface AlertRules {
  deadline_warning_days: number;
  cash_gap_forecast_days: number;
  notify_on_critical_instant: boolean;
}

export interface TelegramSettings {
  telegram_bot_enabled: boolean;
  bot_username: string;
  group_channel_connected: boolean;
  daily_digest_enabled: boolean;
  daily_digest_time: string;
  alert_rules: AlertRules;
}

// --- Google Drive Sync ---
export interface DriveSyncResult {
  status: 'success' | 'idle' | 'syncing' | 'error';
  synced_files_count: number;
  new_alerts_count: number;
  last_synced_at: string;
  message?: string;
}

export interface DriveSyncStatus {
  last_synced_at: string;
  synced_files_count: number;
  status: 'idle' | 'syncing' | 'error';
  target_folders_count?: number;
}

export * from './roles';

