ALTER TABLE "申请单基本信息" DROP COLUMN IF EXISTS source_system;
ALTER TABLE "申请单基本信息" DROP COLUMN IF EXISTS raw_payload;

ALTER TABLE "申请单权限列表" ADD COLUMN IF NOT EXISTS org_scope_count INTEGER;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = '申请单权限列表'
          AND column_name = 'administrative_org_detail_text'
    ) THEN
        UPDATE "申请单权限列表"
        SET org_scope_count = COALESCE(
            org_scope_count,
            CASE
                WHEN substring(administrative_org_detail_text from '\(([0-9]+)\)') IS NULL THEN NULL
                ELSE substring(administrative_org_detail_text from '\(([0-9]+)\)')::INTEGER
            END
        );
    END IF;
END $$;

ALTER TABLE "申请单权限列表" DROP COLUMN IF EXISTS raw_row;
ALTER TABLE "申请单权限列表" DROP COLUMN IF EXISTS salary_change_reason;
ALTER TABLE "申请单权限列表" DROP COLUMN IF EXISTS tax_unit;
ALTER TABLE "申请单权限列表" DROP COLUMN IF EXISTS business_project;
ALTER TABLE "申请单权限列表" DROP COLUMN IF EXISTS social_security_unit_detail;
ALTER TABLE "申请单权限列表" DROP COLUMN IF EXISTS same_role_multi_dimension_flag;
ALTER TABLE "申请单权限列表" DROP COLUMN IF EXISTS administrative_org_text;
ALTER TABLE "申请单权限列表" DROP COLUMN IF EXISTS position_text;
ALTER TABLE "申请单权限列表" DROP COLUMN IF EXISTS administrative_org_detail_text;
