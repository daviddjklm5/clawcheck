CREATE TABLE IF NOT EXISTS "组织列表" (
    org_code TEXT PRIMARY KEY,
    row_no INTEGER,
    org_name TEXT,
    org_type TEXT,
    parent_org_name TEXT,
    parent_org_code TEXT,
    company_name TEXT,
    org_level TEXT,
    city_name TEXT,
    physical_level TEXT,
    dept_subcategory_code TEXT,
    dept_subcategory_name TEXT,
    dept_category_code TEXT,
    dept_category_name TEXT,
    org_full_name TEXT,
    org_manager_name TEXT,
    hr_owner_employee_no TEXT,
    hr_owner_name TEXT,
    hr_owner_include_children_flag TEXT,
    hr_owner_exposed_flag TEXT,
    source_root_org TEXT,
    include_all_children BOOLEAN NOT NULL DEFAULT TRUE,
    source_file_name TEXT,
    import_batch_no TEXT,
    extra_columns_json JSONB NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE "组织列表" ADD COLUMN IF NOT EXISTS extra_columns_json JSONB NULL;

CREATE INDEX IF NOT EXISTS idx_组织列表_parent_org_code ON "组织列表" (parent_org_code);
CREATE INDEX IF NOT EXISTS idx_组织列表_import_batch_no ON "组织列表" (import_batch_no);
