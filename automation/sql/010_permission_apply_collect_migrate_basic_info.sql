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
                "单据编号",
                "工号",
                "权限对象",
                "申请理由",
                "单据状态",
                "人事管理组织",
                "公司",
                "部门",
                "职位",
                "申请日期",
                "记录创建时间",
                "记录更新时间"
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
            ON CONFLICT ("单据编号") DO UPDATE SET
                "工号" = EXCLUDED."工号",
                "权限对象" = EXCLUDED."权限对象",
                "申请理由" = EXCLUDED."申请理由",
                "单据状态" = EXCLUDED."单据状态",
                "人事管理组织" = EXCLUDED."人事管理组织",
                "公司" = EXCLUDED."公司",
                "部门" = EXCLUDED."部门",
                "职位" = EXCLUDED."职位",
                "申请日期" = EXCLUDED."申请日期",
                "记录创建时间" = LEAST("申请单基本信息"."记录创建时间", EXCLUDED."记录创建时间"),
                "记录更新时间" = GREATEST("申请单基本信息"."记录更新时间", EXCLUDED."记录更新时间")
        $sql$;

        IF to_regclass(format('%I.%I', current_schema(), 'permission_apply_detail')) IS NOT NULL THEN
            EXECUTE '
                DELETE FROM "申请单权限列表"
                WHERE "单据编号" IN (
                    SELECT DISTINCT document_no
                    FROM permission_apply_detail
                )
            ';
            EXECUTE '
                INSERT INTO "申请单权限列表" (
                    "单据编号",
                    "明细行号",
                    "申请类型",
                    "角色名称",
                    "角色描述",
                    "角色编码",
                    "参保单位",
                    "组织范围数量",
                    "记录创建时间",
                    "记录更新时间"
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
                WHERE "单据编号" IN (
                    SELECT DISTINCT document_no
                    FROM approval_record
                )
            ';
            EXECUTE '
                INSERT INTO "申请单审批记录" (
                    "单据编号",
                    "审批记录顺序号",
                    "节点名称",
                    "审批人",
                    "审批人组织或职位",
                    "审批动作",
                    "审批意见",
                    "审批时间",
                    "原始展示文本",
                    "记录创建时间"
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
                INSERT INTO "申请表组织范围" ("单据编号", "组织编码", "记录创建时间")
                SELECT document_no, org_code, created_at
                FROM organization_code
                ON CONFLICT ("单据编号", "组织编码") DO NOTHING
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
            FOREIGN KEY ("单据编号")
            REFERENCES "申请单基本信息"("单据编号")
            ON DELETE CASCADE
        ';
    END IF;

    IF old_basic_info_exists THEN
        EXECUTE 'DROP TABLE IF EXISTS permission_apply_detail';
        EXECUTE 'DROP TABLE IF EXISTS approval_record';
        EXECUTE 'DROP TABLE basic_info';
    END IF;
END $$;
