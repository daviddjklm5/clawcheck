DO $$
DECLARE
    old_table_exists BOOLEAN;
    new_table_exists BOOLEAN;
    fk_name TEXT;
BEGIN
    SELECT to_regclass(format('%I.%I', current_schema(), 'basic_info')) IS NOT NULL
    INTO old_table_exists;

    SELECT to_regclass(format('%I.%I', current_schema(), '申请单基本信息')) IS NOT NULL
    INTO new_table_exists;

    IF NOT old_table_exists OR NOT new_table_exists THEN
        RETURN;
    END IF;

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
            source_system,
            raw_payload,
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
            source_system,
            raw_payload,
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
            source_system = EXCLUDED.source_system,
            raw_payload = EXCLUDED.raw_payload,
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
                same_role_multi_dimension_flag,
                administrative_org_text,
                administrative_org_detail_text,
                position_text,
                social_security_unit,
                social_security_unit_detail,
                business_project,
                tax_unit,
                salary_change_reason,
                raw_row,
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
                same_role_multi_dimension_flag,
                administrative_org_text,
                administrative_org_detail_text,
                position_text,
                social_security_unit,
                social_security_unit_detail,
                business_project,
                tax_unit,
                salary_change_reason,
                raw_row,
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

    IF to_regclass(format('%I.%I', current_schema(), 'organization_code')) IS NOT NULL THEN
        FOR fk_name IN
            SELECT con.conname
            FROM pg_constraint con
            JOIN pg_class rel
              ON rel.oid = con.conrelid
            JOIN pg_namespace nsp
              ON nsp.oid = rel.relnamespace
            WHERE con.contype = 'f'
              AND nsp.nspname = current_schema()
              AND rel.relname = 'organization_code'
        LOOP
            EXECUTE format('ALTER TABLE organization_code DROP CONSTRAINT %I', fk_name);
        END LOOP;

        EXECUTE '
            ALTER TABLE organization_code
            ADD CONSTRAINT organization_code_document_no_fkey
            FOREIGN KEY (document_no)
            REFERENCES "申请单基本信息"(document_no)
            ON DELETE CASCADE
        ';
    END IF;

    EXECUTE 'DROP TABLE IF EXISTS permission_apply_detail';
    EXECUTE 'DROP TABLE IF EXISTS approval_record';
    EXECUTE 'DROP TABLE basic_info';
END $$;
