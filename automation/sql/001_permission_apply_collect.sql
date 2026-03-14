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
    social_security_unit TEXT,
    org_scope_count INTEGER,
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

CREATE TABLE IF NOT EXISTS "申请表组织范围" (
    id BIGSERIAL PRIMARY KEY,
    document_no VARCHAR(64) NOT NULL REFERENCES "申请单基本信息"(document_no) ON DELETE CASCADE,
    org_code VARCHAR(64) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_apply_form_org_scope UNIQUE (document_no, org_code)
);

CREATE INDEX IF NOT EXISTS idx_apply_form_permission_list_document_no ON "申请单权限列表"(document_no);
CREATE INDEX IF NOT EXISTS idx_apply_form_approval_record_document_no ON "申请单审批记录"(document_no);
CREATE INDEX IF NOT EXISTS idx_apply_form_org_scope_document_no ON "申请表组织范围"(document_no);
