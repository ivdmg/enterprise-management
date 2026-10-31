-- ============================================================================
-- Проект: Smart Enterprise Hub (MVP)
-- СУБД: PostgreSQL 16+
-- Описание: Продакшн-скрипт создания схемы базы данных
-- ============================================================================

-- Включение расширения для генерации UUID v4
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ----------------------------------------------------------------------------
-- 1. Пользовательские типы данных (ENUMs)
-- ----------------------------------------------------------------------------

DO $$ BEGIN
    CREATE TYPE user_role_enum AS ENUM ('admin', 'manager', 'viewer');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE file_status_enum AS ENUM (
        'uploaded', 
        'profiling', 
        'awaiting_confirmation', 
        'processed', 
        'failed'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE domain_category_enum AS ENUM (
        'production_tenders', 
        'cashflow_debt', 
        'payroll_hr', 
        'operational_tasks'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE project_risk_enum AS ENUM ('normal', 'warning', 'critical');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE cashflow_direction_enum AS ENUM ('incoming', 'outgoing');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE payroll_status_enum AS ENUM ('accrued', 'partially_paid', 'paid', 'overdue');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE task_priority_enum AS ENUM ('low', 'medium', 'high', 'urgent');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE task_status_enum AS ENUM ('pending', 'in_progress', 'completed', 'overdue');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE alert_severity_enum AS ENUM ('CRITICAL', 'WARNING', 'INFO');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE notification_channel_enum AS ENUM ('IN_APP', 'TELEGRAM', 'EMAIL');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE notification_status_enum AS ENUM ('PENDING', 'SENT', 'FAILED');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- ----------------------------------------------------------------------------
-- 2. Вспомогательная функция триггера обновления updated_at
-- ----------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION trigger_set_timestamp()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ----------------------------------------------------------------------------
-- 3. Таблицы ядра мультиарендности и пользователей
-- ----------------------------------------------------------------------------

-- Компании-клиенты (Тенанты)
CREATE TABLE IF NOT EXISTS companies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    inn VARCHAR(12),
    kpp VARCHAR(9),
    timezone VARCHAR(50) DEFAULT 'Europe/Moscow',
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TRIGGER set_timestamp_companies
BEFORE UPDATE ON companies
FOR EACH ROW EXECUTE PROCEDURE trigger_set_timestamp();

-- Пользователи системы
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    email VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    role user_role_enum NOT NULL DEFAULT 'viewer',
    telegram_chat_id BIGINT,
    is_active BOOLEAN NOT NULL DEFAULT true,
    last_login_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT uq_users_email UNIQUE (email)
);

CREATE INDEX idx_users_company ON users(company_id);
CREATE INDEX idx_users_telegram ON users(telegram_chat_id) WHERE telegram_chat_id IS NOT NULL;

CREATE TRIGGER set_timestamp_users
BEFORE UPDATE ON users
FOR EACH ROW EXECUTE PROCEDURE trigger_set_timestamp();

-- ----------------------------------------------------------------------------
-- 4. Хранилище файлов и кэш схем парсинга
-- ----------------------------------------------------------------------------

-- Реестр загруженных файлов
CREATE TABLE IF NOT EXISTS uploaded_files (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    uploaded_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    original_name VARCHAR(255) NOT NULL,
    storage_path VARCHAR(500) NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    mime_type VARCHAR(100) NOT NULL,
    sha256_hash VARCHAR(64) NOT NULL,
    status file_status_enum NOT NULL DEFAULT 'uploaded',
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    deleted_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_uploaded_files_company_hash ON uploaded_files(company_id, sha256_hash);
CREATE INDEX idx_uploaded_files_status ON uploaded_files(company_id, status);

CREATE TRIGGER set_timestamp_uploaded_files
BEFORE UPDATE ON uploaded_files
FOR EACH ROW EXECUTE PROCEDURE trigger_set_timestamp();

-- Кэш шаблонов и маппинга колонок (Fingerprint Cache)
CREATE TABLE IF NOT EXISTS file_templates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    template_name VARCHAR(255) NOT NULL,
    sheet_name VARCHAR(255) DEFAULT 'Sheet1',
    headers_fingerprint VARCHAR(64) NOT NULL,
    domain_category domain_category_enum NOT NULL,
    column_mapping JSONB NOT NULL,
    confidence_score NUMERIC(5, 2) DEFAULT 1.00,
    match_count INT NOT NULL DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT uq_company_fingerprint UNIQUE (company_id, headers_fingerprint)
);

CREATE INDEX idx_templates_lookup ON file_templates(company_id, headers_fingerprint);
CREATE INDEX idx_templates_mapping_gin ON file_templates USING GIN (column_mapping);

CREATE TRIGGER set_timestamp_file_templates
BEFORE UPDATE ON file_templates
FOR EACH ROW EXECUTE PROCEDURE trigger_set_timestamp();

-- Журнал задач парсинга
CREATE TABLE IF NOT EXISTS parsing_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    file_id UUID NOT NULL REFERENCES uploaded_files(id) ON DELETE CASCADE,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    finished_at TIMESTAMP WITH TIME ZONE,
    status VARCHAR(30) NOT NULL DEFAULT 'in_progress',
    confidence_score NUMERIC(5, 2),
    ai_model_used VARCHAR(50),
    extracted_rows_count INT DEFAULT 0,
    detected_headers JSONB,
    execution_time_ms INT,
    error_log TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_parsing_jobs_file ON parsing_jobs(file_id);

-- ----------------------------------------------------------------------------
-- 5. Канонические доменные таблицы (Business Entities)
-- ----------------------------------------------------------------------------

-- Домен 1: Тендеры, СМР и проектные обязательства
CREATE TABLE IF NOT EXISTS tender_projects (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    file_id UUID REFERENCES uploaded_files(id) ON DELETE SET NULL,
    project_code VARCHAR(100),
    project_name VARCHAR(500) NOT NULL,
    customer_name VARCHAR(255),
    curator_name VARCHAR(255),
    contract_sum NUMERIC(15, 2) NOT NULL DEFAULT 0.00,
    completed_sum NUMERIC(15, 2) NOT NULL DEFAULT 0.00,
    paid_sum NUMERIC(15, 2) NOT NULL DEFAULT 0.00,
    debt_sum NUMERIC(15, 2) NOT NULL DEFAULT 0.00,
    start_date DATE,
    deadline_date DATE,
    actual_completion_date DATE,
    status VARCHAR(50) NOT NULL DEFAULT 'in_progress',
    risk_level project_risk_enum NOT NULL DEFAULT 'normal',
    penalty_amount_calculated NUMERIC(15, 2) NOT NULL DEFAULT 0.00,
    custom_attributes JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    deleted_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_tender_company_status ON tender_projects(company_id, status, deadline_date) WHERE deleted_at IS NULL;
CREATE INDEX idx_tender_risk ON tender_projects(company_id, risk_level) WHERE risk_level != 'normal';

CREATE TRIGGER set_timestamp_tender_projects
BEFORE UPDATE ON tender_projects
FOR EACH ROW EXECUTE PROCEDURE trigger_set_timestamp();

-- Домен 2: Финансы, касса и взаиморасчеты
CREATE TABLE IF NOT EXISTS cashflow_operations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    file_id UUID REFERENCES uploaded_files(id) ON DELETE SET NULL,
    operation_date DATE NOT NULL,
    counterparty VARCHAR(255),
    direction cashflow_direction_enum NOT NULL,
    category VARCHAR(100),
    planned_amount NUMERIC(15, 2) NOT NULL DEFAULT 0.00,
    actual_amount NUMERIC(15, 2) NOT NULL DEFAULT 0.00,
    is_paid BOOLEAN NOT NULL DEFAULT false,
    account_name VARCHAR(100),
    payment_due_date DATE,
    document_number VARCHAR(100),
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    deleted_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_cashflow_company_date ON cashflow_operations(company_id, operation_date, direction) WHERE deleted_at IS NULL;
CREATE INDEX idx_cashflow_due_unpaid ON cashflow_operations(company_id, payment_due_date) WHERE is_paid = false;

CREATE TRIGGER set_timestamp_cashflow_operations
BEFORE UPDATE ON cashflow_operations
FOR EACH ROW EXECUTE PROCEDURE trigger_set_timestamp();

-- Домен 3: ФОТ, начисления и выплаты сотрудникам
CREATE TABLE IF NOT EXISTS payroll_records (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    file_id UUID REFERENCES uploaded_files(id) ON DELETE SET NULL,
    payroll_period VARCHAR(20) NOT NULL, -- Формат: 'YYYY-MM'
    employee_name VARCHAR(255) NOT NULL,
    department VARCHAR(150),
    role_title VARCHAR(150),
    accrued_amount NUMERIC(15, 2) NOT NULL DEFAULT 0.00,
    paid_amount NUMERIC(15, 2) NOT NULL DEFAULT 0.00,
    debt_amount NUMERIC(15, 2) NOT NULL DEFAULT 0.00,
    payment_due_date DATE,
    status payroll_status_enum NOT NULL DEFAULT 'accrued',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    deleted_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_payroll_company_period ON payroll_records(company_id, payroll_period) WHERE deleted_at IS NULL;
CREATE INDEX idx_payroll_debt ON payroll_records(company_id, status) WHERE status = 'overdue';

CREATE TRIGGER set_timestamp_payroll_records
BEFORE UPDATE ON payroll_records
FOR EACH ROW EXECUTE PROCEDURE trigger_set_timestamp();

-- Домен 4: Операционные поручения, предписания и комплаенс
CREATE TABLE IF NOT EXISTS operational_tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    file_id UUID REFERENCES uploaded_files(id) ON DELETE SET NULL,
    task_title VARCHAR(500) NOT NULL,
    description TEXT,
    responsible_person VARCHAR(255),
    due_date DATE,
    status task_status_enum NOT NULL DEFAULT 'pending',
    priority task_priority_enum NOT NULL DEFAULT 'medium',
    penalty_risk_desc TEXT,
    estimated_penalty_amount NUMERIC(15, 2) NOT NULL DEFAULT 0.00,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    deleted_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_tasks_company_due ON operational_tasks(company_id, due_date, status) WHERE deleted_at IS NULL;

CREATE TRIGGER set_timestamp_operational_tasks
BEFORE UPDATE ON operational_tasks
FOR EACH ROW EXECUTE PROCEDURE trigger_set_timestamp();

-- ----------------------------------------------------------------------------
-- 6. Система выявления рисков, алертов и уведомлений
-- ----------------------------------------------------------------------------

-- Реестр инцидентов и алертов
CREATE TABLE IF NOT EXISTS system_alerts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    domain_category domain_category_enum NOT NULL,
    severity alert_severity_enum NOT NULL,
    alert_type VARCHAR(50) NOT NULL, -- 'DEADLINE_BREACH', 'CASH_GAP', 'WAGE_OVERDUE'
    entity_type VARCHAR(50), -- 'tender_projects', 'cashflow_operations'
    entity_id UUID,
    title VARCHAR(300) NOT NULL,
    description TEXT NOT NULL,
    calculated_financial_impact NUMERIC(15, 2) NOT NULL DEFAULT 0.00,
    trigger_date DATE NOT NULL DEFAULT CURRENT_DATE,
    is_resolved BOOLEAN NOT NULL DEFAULT false,
    resolved_at TIMESTAMP WITH TIME ZONE,
    resolved_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    resolution_comment TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_alerts_company_unresolved ON system_alerts(company_id, is_resolved, severity);
CREATE INDEX idx_alerts_date ON system_alerts(company_id, trigger_date DESC);

CREATE TRIGGER set_timestamp_system_alerts
BEFORE UPDATE ON system_alerts
FOR EACH ROW EXECUTE PROCEDURE trigger_set_timestamp();

-- Журнал доставки уведомлений
CREATE TABLE IF NOT EXISTS notification_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    alert_id UUID NOT NULL REFERENCES system_alerts(id) ON DELETE CASCADE,
    channel notification_channel_enum NOT NULL,
    recipient_target VARCHAR(255) NOT NULL, -- chat_id или email
    status notification_status_enum NOT NULL DEFAULT 'PENDING',
    error_message TEXT,
    sent_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_notification_logs_alert ON notification_logs(alert_id);

-- Настройки интеграций компании
CREATE TABLE IF NOT EXISTS integration_settings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL UNIQUE REFERENCES companies(id) ON DELETE CASCADE,
    telegram_bot_enabled BOOLEAN NOT NULL DEFAULT false,
    telegram_bot_token VARCHAR(255),
    telegram_channel_id BIGINT,
    daily_digest_enabled BOOLEAN NOT NULL DEFAULT true,
    daily_digest_time VARCHAR(5) NOT NULL DEFAULT '08:30',
    alert_rules JSONB DEFAULT '{
        "deadline_warning_days": 5,
        "cash_gap_forecast_days": 14,
        "notify_on_critical_instant": true
    }'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TRIGGER set_timestamp_integration_settings
BEFORE UPDATE ON integration_settings
FOR EACH ROW EXECUTE PROCEDURE trigger_set_timestamp();

-- ----------------------------------------------------------------------------
-- 7. Демо-данные для локального тестирования (Initial Seed)
-- ----------------------------------------------------------------------------

-- Создание тестовой компании
INSERT INTO companies (id, name, inn, timezone)
VALUES ('a0000000-0000-0000-0000-000000000001', 'ООО "ГлавСтройМонтаж"', '7701234567', 'Europe/Moscow')
ON CONFLICT DO NOTHING;

-- Создание администратора компании (пароль: 'Admin123!' -> хэш bcrypt)
INSERT INTO users (id, company_id, email, password_hash, full_name, role)
VALUES (
    'b0000000-0000-0000-0000-000000000001',
    'a0000000-0000-0000-0000-000000000001',
    'admin@glavstroy.ru',
    '$2b$12$e8Z4sT2uXhVdCkqyR0l4AOB2x3e29oQ8u3Z81u30vC8uG1R0mK.9i',
    'Алексей Викторович (Генеральный)',
    'admin'
)
ON CONFLICT DO NOTHING;

-- Создание базовых настроек интеграций компании
INSERT INTO integration_settings (company_id, telegram_bot_enabled, daily_digest_time)
VALUES ('a0000000-0000-0000-0000-000000000001', false, '08:30')
ON CONFLICT DO NOTHING;
