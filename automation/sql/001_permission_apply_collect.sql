CREATE TABLE IF NOT EXISTS "申请单基本信息" (
    document_no VARCHAR(64) PRIMARY KEY,
    employee_no VARCHAR(64) NOT NULL,
    permission_target VARCHAR(128) NOT NULL,
    apply_reason TEXT,
    document_status VARCHAR(64),
    hr_org VARCHAR(128),
    company_name VARCHAR(128),
    department_name VARCHAR(128),
    position_name VARCHAR(128),
    apply_time TIMESTAMP NULL,
    source_system VARCHAR(32) DEFAULT 'iERP',
    raw_payload JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS "申请单权限列表" (
    id BIGSERIAL PRIMARY KEY,
    document_no VARCHAR(64) NOT NULL REFERENCES "申请单基本信息"(document_no) ON DELETE CASCADE,
    line_no VARCHAR(32),
    apply_type VARCHAR(128),
    role_name VARCHAR(255),
    role_desc TEXT,
    role_code VARCHAR(128),
    same_role_multi_dimension_flag VARCHAR(32),
    administrative_org_text TEXT,
    administrative_org_detail_text VARCHAR(64),
    position_text TEXT,
    social_security_unit TEXT,
    social_security_unit_detail TEXT,
    business_project TEXT,
    tax_unit TEXT,
    salary_change_reason TEXT,
    raw_row JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_apply_form_permission_list UNIQUE (document_no, line_no)
);

CREATE TABLE IF NOT EXISTS "申请单审批记录" (
    id BIGSERIAL PRIMARY KEY,
    document_no VARCHAR(64) NOT NULL REFERENCES "申请单基本信息"(document_no) ON DELETE CASCADE,
    record_seq INTEGER,
    node_name VARCHAR(128),
    approver_name VARCHAR(128),
    approver_org_or_position VARCHAR(255),
    approval_action VARCHAR(64),
    approval_opinion TEXT,
    approval_time TIMESTAMP NULL,
    raw_text TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS organization_code (
    id BIGSERIAL PRIMARY KEY,
    document_no VARCHAR(64) NOT NULL REFERENCES "申请单基本信息"(document_no) ON DELETE CASCADE,
    org_code VARCHAR(64) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_organization_code UNIQUE (document_no, org_code)
);

CREATE INDEX IF NOT EXISTS idx_apply_form_permission_list_document_no ON "申请单权限列表"(document_no);
CREATE INDEX IF NOT EXISTS idx_apply_form_approval_record_document_no ON "申请单审批记录"(document_no);
CREATE INDEX IF NOT EXISTS idx_organization_code_document_no ON organization_code(document_no);
