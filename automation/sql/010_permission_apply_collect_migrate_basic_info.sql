DO $$
DECLARE
    old_basic_info_exists BOOLEAN;
    new_basic_info_exists BOOLEAN;
    fk_name TEXT;
BEGIN
    SELECT to_regclass(format('%I.%I', current_schema(), 'basic_info')) IS NOT NULL
    INTO old_basic_info_exists;

    SELECT to_regclass(format('%I.%I', current_schema(), '申请单基本信息')) IS NOT NULL
    INTO new_basic_info_exists;

    IF old_basic_info_exists AND new_basic_info_exists THEN
        EXECUTE $sql$
            INSERT INTO "申请单基本信息" (
                document_no,
                employee_no,
                permission_target,
                apply_reason,
                document_status,
                hr_org,
                company_name,
                department_name,
                position_name,
                apply_time,
                created_at,
                updated_at
            )
            SELECT
                document_no,
                employee_no,
                permission_target,
                apply_reason,
                document_status,
                hr_org,
                company_name,
                department_name,
                position_name,
                apply_time,
                created_at,
                updated_at
            FROM basic_info
            ON CONFLICT (document_no) DO UPDATE SET
                employee_no = EXCLUDED.employee_no,
                permission_target = EXCLUDED.permission_target,
                apply_reason = EXCLUDED.apply_reason,
                document_status = EXCLUDED.document_status,
                hr_org = EXCLUDED.hr_org,
                company_name = EXCLUDED.company_name,
                department_name = EXCLUDED.department_name,
                position_name = EXCLUDED.position_name,
                apply_time = EXCLUDED.apply_time,
                created_at = LEAST("申请单基本信息".created_at, EXCLUDED.created_at),
                updated_at = GREATEST("申请单基本信息".updated_at, EXCLUDED.updated_at)
        $sql$;

        IF to_regclass(format('%I.%I', current_schema(), 'permission_apply_detail')) IS NOT NULL THEN
            EXECUTE '
                DELETE FROM "申请单权限列表"
                WHERE document_no IN (
                    SELECT DISTINCT document_no
                    FROM permission_apply_detail
                )
            ';
            EXECUTE '
                INSERT INTO "申请单权限列表" (
                    document_no,
                    line_no,
                    apply_type,
                    role_name,
                    role_desc,
                    role_code,
                    social_security_unit,
                    org_scope_count,
                    created_at,
                    updated_at
                )
                SELECT
                    document_no,
                    line_no,
                    apply_type,
                    role_name,
                    role_desc,
                    role_code,
                    social_security_unit,
                    CASE
                        WHEN substring(administrative_org_detail_text from ''\(([0-9]+)\)'') IS NULL THEN NULL
                        ELSE substring(administrative_org_detail_text from ''\(([0-9]+)\)'')::INTEGER
                    END AS org_scope_count,
                    created_at,
                    updated_at
                FROM permission_apply_detail
            ';
        END IF;

        IF to_regclass(format('%I.%I', current_schema(), 'approval_record')) IS NOT NULL THEN
            EXECUTE '
                DELETE FROM "申请单审批记录"
                WHERE document_no IN (
                    SELECT DISTINCT document_no
                    FROM approval_record
                )
            ';
            EXECUTE '
                INSERT INTO "申请单审批记录" (
                    document_no,
                    record_seq,
                    node_name,
                    approver_name,
                    approver_org_or_position,
                    approval_action,
                    approval_opinion,
                    approval_time,
                    raw_text,
                    created_at
                )
                SELECT
                    document_no,
                    record_seq,
                    node_name,
                    approver_name,
                    approver_org_or_position,
                    approval_action,
                    approval_opinion,
                    approval_time,
                    raw_text,
                    created_at
                FROM approval_record
            ';
        END IF;
    END IF;

    IF to_regclass(format('%I.%I', current_schema(), 'organization_code')) IS NOT NULL THEN
        IF to_regclass(format('%I.%I', current_schema(), '申请表组织范围')) IS NULL THEN
            EXECUTE 'ALTER TABLE organization_code RENAME TO "申请表组织范围"';
        ELSE
            EXECUTE '
                INSERT INTO "申请表组织范围" (document_no, org_code, created_at)
                SELECT document_no, org_code, created_at
                FROM organization_code
                ON CONFLICT (document_no, org_code) DO NOTHING
            ';
            EXECUTE 'DROP TABLE organization_code';
        END IF;
    END IF;

    IF to_regclass(format('%I.%I', current_schema(), '申请表组织范围')) IS NOT NULL THEN
        FOR fk_name IN
            SELECT con.conname
            FROM pg_constraint con
            JOIN pg_class rel
              ON rel.oid = con.conrelid
            JOIN pg_namespace nsp
              ON nsp.oid = rel.relnamespace
            WHERE con.contype = 'f'
              AND nsp.nspname = current_schema()
              AND rel.relname = '申请表组织范围'
        LOOP
            EXECUTE format('ALTER TABLE "申请表组织范围" DROP CONSTRAINT %I', fk_name);
        END LOOP;

        EXECUTE '
            ALTER TABLE "申请表组织范围"
            ADD CONSTRAINT apply_form_org_scope_document_no_fkey
            FOREIGN KEY (document_no)
            REFERENCES "申请单基本信息"(document_no)
            ON DELETE CASCADE
        ';
    END IF;

    IF to_regclass(format('%I.%I', current_schema(), '申请单基本信息')) IS NOT NULL THEN
        EXECUTE 'ALTER TABLE "申请单基本信息" DROP COLUMN IF EXISTS source_system';
        EXECUTE 'ALTER TABLE "申请单基本信息" DROP COLUMN IF EXISTS raw_payload';
    END IF;

    IF to_regclass(format('%I.%I', current_schema(), '申请单权限列表')) IS NOT NULL THEN
        EXECUTE 'ALTER TABLE "申请单权限列表" ADD COLUMN IF NOT EXISTS org_scope_count INTEGER';

        IF EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = '申请单权限列表'
              AND column_name = 'administrative_org_detail_text'
        ) THEN
            EXECUTE '
                UPDATE "申请单权限列表"
                SET org_scope_count = COALESCE(
                    org_scope_count,
                    CASE
                        WHEN substring(administrative_org_detail_text from ''\(([0-9]+)\)'') IS NULL THEN NULL
                        ELSE substring(administrative_org_detail_text from ''\(([0-9]+)\)'')::INTEGER
                    END
                )
            ';
        END IF;

        EXECUTE 'ALTER TABLE "申请单权限列表" DROP COLUMN IF EXISTS raw_row';
        EXECUTE 'ALTER TABLE "申请单权限列表" DROP COLUMN IF EXISTS salary_change_reason';
        EXECUTE 'ALTER TABLE "申请单权限列表" DROP COLUMN IF EXISTS tax_unit';
        EXECUTE 'ALTER TABLE "申请单权限列表" DROP COLUMN IF EXISTS business_project';
        EXECUTE 'ALTER TABLE "申请单权限列表" DROP COLUMN IF EXISTS social_security_unit_detail';
        EXECUTE 'ALTER TABLE "申请单权限列表" DROP COLUMN IF EXISTS same_role_multi_dimension_flag';
        EXECUTE 'ALTER TABLE "申请单权限列表" DROP COLUMN IF EXISTS administrative_org_text';
        EXECUTE 'ALTER TABLE "申请单权限列表" DROP COLUMN IF EXISTS position_text';
        EXECUTE 'ALTER TABLE "申请单权限列表" DROP COLUMN IF EXISTS administrative_org_detail_text';
    END IF;

    IF old_basic_info_exists THEN
        EXECUTE 'DROP TABLE IF EXISTS permission_apply_detail';
        EXECUTE 'DROP TABLE IF EXISTS approval_record';
        EXECUTE 'DROP TABLE basic_info';
    END IF;
END $$;
