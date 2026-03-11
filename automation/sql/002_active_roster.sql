CREATE TABLE IF NOT EXISTS "在职花名册表" (
    id BIGSERIAL PRIMARY KEY,
    query_date DATE NOT NULL,
    employee_no VARCHAR(64) NOT NULL,
    employee_name VARCHAR(128),
    company_name VARCHAR(255),
    company_id VARCHAR(64),
    department_name VARCHAR(255),
    department_long_text TEXT,
    department_id VARCHAR(64),
    department_city VARCHAR(128),
    entry_date DATE NULL,
    level1_function_name VARCHAR(128),
    position_code VARCHAR(64),
    position_name VARCHAR(255),
    specific_post_name VARCHAR(255),
    critical_post_flag VARCHAR(32),
    post_family VARCHAR(64),
    job_title VARCHAR(128),
    level2_function_name VARCHAR(128),
    standard_position_code VARCHAR(64),
    source_file_name VARCHAR(255) NOT NULL,
    import_batch_no VARCHAR(64) NOT NULL,
    row_no INTEGER,
    raw_row_json JSONB NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_active_roster_query_employee UNIQUE (query_date, employee_no)
);

CREATE INDEX IF NOT EXISTS idx_active_roster_query_date ON "在职花名册表"(query_date);
CREATE INDEX IF NOT EXISTS idx_active_roster_department_id ON "在职花名册表"(department_id);
CREATE INDEX IF NOT EXISTS idx_active_roster_company_id ON "在职花名册表"(company_id);
