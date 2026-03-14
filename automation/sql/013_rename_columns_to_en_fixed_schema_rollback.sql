-- 方案011D：固定字段中文化物理改列（回滚）
-- 说明：
-- 1. 本脚本用于撤销 012_rename_columns_to_cn_fixed_schema.sql。
-- 2. 本脚本同时回滚 refresh_组织属性查询() 到英文列名版本。

BEGIN;

ALTER TABLE "申请单基本信息" RENAME COLUMN "单据编号" TO document_no;
ALTER TABLE "申请单基本信息" RENAME COLUMN "工号" TO employee_no;
ALTER TABLE "申请单基本信息" RENAME COLUMN "权限对象" TO permission_target;
ALTER TABLE "申请单基本信息" RENAME COLUMN "申请理由" TO apply_reason;
ALTER TABLE "申请单基本信息" RENAME COLUMN "单据状态" TO document_status;
ALTER TABLE "申请单基本信息" RENAME COLUMN "人事管理组织" TO hr_org;
ALTER TABLE "申请单基本信息" RENAME COLUMN "公司" TO company_name;
ALTER TABLE "申请单基本信息" RENAME COLUMN "部门" TO department_name;
ALTER TABLE "申请单基本信息" RENAME COLUMN "职位" TO position_name;
ALTER TABLE "申请单基本信息" RENAME COLUMN "申请日期" TO apply_time;
ALTER TABLE "申请单基本信息" RENAME COLUMN "最新审批时间" TO latest_approval_time;
ALTER TABLE "申请单基本信息" RENAME COLUMN "记录创建时间" TO created_at;
ALTER TABLE "申请单基本信息" RENAME COLUMN "记录更新时间" TO updated_at;

ALTER TABLE "申请单权限列表" RENAME COLUMN "权限明细ID" TO id;
ALTER TABLE "申请单权限列表" RENAME COLUMN "单据编号" TO document_no;
ALTER TABLE "申请单权限列表" RENAME COLUMN "明细行号" TO line_no;
ALTER TABLE "申请单权限列表" RENAME COLUMN "申请类型" TO apply_type;
ALTER TABLE "申请单权限列表" RENAME COLUMN "角色名称" TO role_name;
ALTER TABLE "申请单权限列表" RENAME COLUMN "角色描述" TO role_desc;
ALTER TABLE "申请单权限列表" RENAME COLUMN "角色编码" TO role_code;
ALTER TABLE "申请单权限列表" RENAME COLUMN "参保单位" TO social_security_unit;
ALTER TABLE "申请单权限列表" RENAME COLUMN "组织范围数量" TO org_scope_count;
ALTER TABLE "申请单权限列表" RENAME COLUMN "记录创建时间" TO created_at;
ALTER TABLE "申请单权限列表" RENAME COLUMN "记录更新时间" TO updated_at;

ALTER TABLE "申请单审批记录" RENAME COLUMN "审批记录ID" TO id;
ALTER TABLE "申请单审批记录" RENAME COLUMN "单据编号" TO document_no;
ALTER TABLE "申请单审批记录" RENAME COLUMN "审批记录顺序号" TO record_seq;
ALTER TABLE "申请单审批记录" RENAME COLUMN "节点名称" TO node_name;
ALTER TABLE "申请单审批记录" RENAME COLUMN "审批人" TO approver_name;
ALTER TABLE "申请单审批记录" RENAME COLUMN "工号" TO approver_employee_no;
ALTER TABLE "申请单审批记录" RENAME COLUMN "审批人组织或职位" TO approver_org_or_position;
ALTER TABLE "申请单审批记录" RENAME COLUMN "审批动作" TO approval_action;
ALTER TABLE "申请单审批记录" RENAME COLUMN "审批意见" TO approval_opinion;
ALTER TABLE "申请单审批记录" RENAME COLUMN "审批时间" TO approval_time;
ALTER TABLE "申请单审批记录" RENAME COLUMN "原始展示文本" TO raw_text;
ALTER TABLE "申请单审批记录" RENAME COLUMN "记录创建时间" TO created_at;

ALTER TABLE "申请表组织范围" RENAME COLUMN "组织范围ID" TO id;
ALTER TABLE "申请表组织范围" RENAME COLUMN "单据编号" TO document_no;
ALTER TABLE "申请表组织范围" RENAME COLUMN "组织编码" TO org_code;
ALTER TABLE "申请表组织范围" RENAME COLUMN "记录创建时间" TO created_at;

ALTER TABLE "在职花名册表" RENAME COLUMN "人员编号" TO employee_no;
ALTER TABLE "在职花名册表" RENAME COLUMN "查询日期" TO query_date;
ALTER TABLE "在职花名册表" RENAME COLUMN "序号" TO serial_no;
ALTER TABLE "在职花名册表" RENAME COLUMN "公司" TO company_name;
ALTER TABLE "在职花名册表" RENAME COLUMN "公司ID" TO company_id;
ALTER TABLE "在职花名册表" RENAME COLUMN "部门" TO department_name;
ALTER TABLE "在职花名册表" RENAME COLUMN "部门长文本" TO department_long_text;
ALTER TABLE "在职花名册表" RENAME COLUMN "部门ID" TO department_id;
ALTER TABLE "在职花名册表" RENAME COLUMN "部门所属城市" TO department_city;
ALTER TABLE "在职花名册表" RENAME COLUMN "姓名" TO employee_name;
ALTER TABLE "在职花名册表" RENAME COLUMN "职位编码" TO position_code;
ALTER TABLE "在职花名册表" RENAME COLUMN "职位名称" TO position_name;
ALTER TABLE "在职花名册表" RENAME COLUMN "具体岗位_新" TO specific_post_name;
ALTER TABLE "在职花名册表" RENAME COLUMN "是否关键岗位" TO critical_post_flag;
ALTER TABLE "在职花名册表" RENAME COLUMN "岗位族" TO post_family;
ALTER TABLE "在职花名册表" RENAME COLUMN "职务" TO job_title;
ALTER TABLE "在职花名册表" RENAME COLUMN "一级职能名称" TO level1_function_name;
ALTER TABLE "在职花名册表" RENAME COLUMN "二级职能名称" TO level2_function_name;
ALTER TABLE "在职花名册表" RENAME COLUMN "标准岗位编码" TO standard_position_code;
ALTER TABLE "在职花名册表" RENAME COLUMN "标准岗位名称" TO standard_position_name;
ALTER TABLE "在职花名册表" RENAME COLUMN "上级编码" TO superior_code;
ALTER TABLE "在职花名册表" RENAME COLUMN "上级名称" TO superior_name;
ALTER TABLE "在职花名册表" RENAME COLUMN "对接HR工号" TO hr_partner_employee_no;
ALTER TABLE "在职花名册表" RENAME COLUMN "对接HR姓名" TO hr_partner_name;
ALTER TABLE "在职花名册表" RENAME COLUMN "班长" TO team_leader_name;
ALTER TABLE "在职花名册表" RENAME COLUMN "员工组" TO employee_group;
ALTER TABLE "在职花名册表" RENAME COLUMN "员工子组" TO employee_subgroup;
ALTER TABLE "在职花名册表" RENAME COLUMN "子标签" TO sub_label;
ALTER TABLE "在职花名册表" RENAME COLUMN "入职日期" TO entry_date;
ALTER TABLE "在职花名册表" RENAME COLUMN "司龄" TO company_seniority_text;
ALTER TABLE "在职花名册表" RENAME COLUMN "性别" TO gender;
ALTER TABLE "在职花名册表" RENAME COLUMN "出生日期" TO birth_date;
ALTER TABLE "在职花名册表" RENAME COLUMN "生日类型" TO birthday_type;
ALTER TABLE "在职花名册表" RENAME COLUMN "实际生日" TO actual_birthday;
ALTER TABLE "在职花名册表" RENAME COLUMN "年龄" TO age_text;
ALTER TABLE "在职花名册表" RENAME COLUMN "户口所在省" TO household_registration_province;
ALTER TABLE "在职花名册表" RENAME COLUMN "户口所在市" TO household_registration_city;
ALTER TABLE "在职花名册表" RENAME COLUMN "户籍地" TO registered_residence;
ALTER TABLE "在职花名册表" RENAME COLUMN "参保地" TO social_security_location;
ALTER TABLE "在职花名册表" RENAME COLUMN "婚姻状况" TO marital_status;
ALTER TABLE "在职花名册表" RENAME COLUMN "学历" TO education_level;
ALTER TABLE "在职花名册表" RENAME COLUMN "学习形式" TO study_mode;
ALTER TABLE "在职花名册表" RENAME COLUMN "毕业时间" TO graduation_date;
ALTER TABLE "在职花名册表" RENAME COLUMN "学位" TO degree;
ALTER TABLE "在职花名册表" RENAME COLUMN "学校" TO school_name;
ALTER TABLE "在职花名册表" RENAME COLUMN "其他院校" TO alternate_school_name;
ALTER TABLE "在职花名册表" RENAME COLUMN "院校专业" TO major_name;
ALTER TABLE "在职花名册表" RENAME COLUMN "证件号码" TO id_number;
ALTER TABLE "在职花名册表" RENAME COLUMN "联系电话" TO phone_number;
ALTER TABLE "在职花名册表" RENAME COLUMN "万科邮箱" TO vanke_email;
ALTER TABLE "在职花名册表" RENAME COLUMN "万物云邮箱" TO onewo_email;
ALTER TABLE "在职花名册表" RENAME COLUMN "域账号" TO domain_account;
ALTER TABLE "在职花名册表" RENAME COLUMN "雇佣状态" TO employment_status;
ALTER TABLE "在职花名册表" RENAME COLUMN "部门分类" TO department_category;
ALTER TABLE "在职花名册表" RENAME COLUMN "部门子分类" TO department_subcategory;
ALTER TABLE "在职花名册表" RENAME COLUMN "是否外盘人员" TO external_roster_flag;
ALTER TABLE "在职花名册表" RENAME COLUMN "合同类型" TO contract_type;
ALTER TABLE "在职花名册表" RENAME COLUMN "合同签订主体" TO contract_signing_entity;
ALTER TABLE "在职花名册表" RENAME COLUMN "合同开始日期" TO contract_start_date;
ALTER TABLE "在职花名册表" RENAME COLUMN "合同结束日期" TO contract_end_date;
ALTER TABLE "在职花名册表" RENAME COLUMN "参加工作时间" TO start_work_date;
ALTER TABLE "在职花名册表" RENAME COLUMN "服务万科时间" TO service_start_date_at_vanke;
ALTER TABLE "在职花名册表" RENAME COLUMN "最新入职万科日期" TO latest_entry_date_to_vanke;
ALTER TABLE "在职花名册表" RENAME COLUMN "司龄起算时间" TO seniority_start_date;
ALTER TABLE "在职花名册表" RENAME COLUMN "工龄" TO working_years_text;
ALTER TABLE "在职花名册表" RENAME COLUMN "储备见习类型" TO trainee_type;
ALTER TABLE "在职花名册表" RENAME COLUMN "储备见习开始日期" TO trainee_start_date;
ALTER TABLE "在职花名册表" RENAME COLUMN "储备见习结束日期" TO trainee_end_date;
ALTER TABLE "在职花名册表" RENAME COLUMN "储备岗位名称" TO trainee_post_name;
ALTER TABLE "在职花名册表" RENAME COLUMN "岗位备注_物业" TO post_remark_property;
ALTER TABLE "在职花名册表" RENAME COLUMN "序列属性" TO sequence_attribute;
ALTER TABLE "在职花名册表" RENAME COLUMN "序列类型" TO sequence_type;
ALTER TABLE "在职花名册表" RENAME COLUMN "组织路径ID" TO org_path_id;
ALTER TABLE "在职花名册表" RENAME COLUMN "组织路径名称" TO org_path_name;
ALTER TABLE "在职花名册表" RENAME COLUMN "合同期限" TO contract_term;
ALTER TABLE "在职花名册表" RENAME COLUMN "是否服过兵役" TO military_service_flag;
ALTER TABLE "在职花名册表" RENAME COLUMN "退役证编号" TO discharge_certificate_no;
ALTER TABLE "在职花名册表" RENAME COLUMN "退伍证类型" TO discharge_certificate_type;
ALTER TABLE "在职花名册表" RENAME COLUMN "入伍时间" TO enlistment_date;
ALTER TABLE "在职花名册表" RENAME COLUMN "退役时间" TO discharge_date;
ALTER TABLE "在职花名册表" RENAME COLUMN "领导力类别" TO leadership_category;
ALTER TABLE "在职花名册表" RENAME COLUMN "证件是否永久有效" TO id_document_permanent_flag;
ALTER TABLE "在职花名册表" RENAME COLUMN "证件有效期起" TO id_document_valid_from;
ALTER TABLE "在职花名册表" RENAME COLUMN "证件有效期止" TO id_document_valid_to;
ALTER TABLE "在职花名册表" RENAME COLUMN "是否主任职" TO primary_position_flag;
ALTER TABLE "在职花名册表" RENAME COLUMN "任职类型" TO employment_type;
ALTER TABLE "在职花名册表" RENAME COLUMN "民族" TO ethnicity;
ALTER TABLE "在职花名册表" RENAME COLUMN "户口性质" TO household_registration_type;
ALTER TABLE "在职花名册表" RENAME COLUMN "户口所在地" TO household_registration_location;
ALTER TABLE "在职花名册表" RENAME COLUMN "出生地" TO birthplace;
ALTER TABLE "在职花名册表" RENAME COLUMN "籍贯" TO native_place;
ALTER TABLE "在职花名册表" RENAME COLUMN "国籍" TO nationality;
ALTER TABLE "在职花名册表" RENAME COLUMN "出生国家" TO birth_country;
ALTER TABLE "在职花名册表" RENAME COLUMN "出生地所在省" TO birthplace_province;
ALTER TABLE "在职花名册表" RENAME COLUMN "出生地所在市" TO birthplace_city;
ALTER TABLE "在职花名册表" RENAME COLUMN "校招届别" TO campus_recruitment_cohort;
ALTER TABLE "在职花名册表" RENAME COLUMN "政治面貌" TO political_status;
ALTER TABLE "在职花名册表" RENAME COLUMN "所属党组织全称" TO party_organization_name;
ALTER TABLE "在职花名册表" RENAME COLUMN "党员状态" TO party_member_status;
ALTER TABLE "在职花名册表" RENAME COLUMN "来源文件名" TO source_file_name;
ALTER TABLE "在职花名册表" RENAME COLUMN "导入批次号" TO import_batch_no;
ALTER TABLE "在职花名册表" RENAME COLUMN "导入行号" TO row_no;
ALTER TABLE "在职花名册表" RENAME COLUMN "下载时间" TO downloaded_at;
ALTER TABLE "在职花名册表" RENAME COLUMN "导入时间" TO imported_at;
ALTER TABLE "在职花名册表" RENAME COLUMN "扩展字段JSON" TO extra_columns_json;
ALTER TABLE "在职花名册表" RENAME COLUMN "记录创建时间" TO created_at;
ALTER TABLE "在职花名册表" RENAME COLUMN "记录更新时间" TO updated_at;

ALTER TABLE "组织列表" RENAME COLUMN "行政组织编码" TO org_code;
ALTER TABLE "组织列表" RENAME COLUMN "序号" TO row_no;
ALTER TABLE "组织列表" RENAME COLUMN "行政组织名称" TO org_name;
ALTER TABLE "组织列表" RENAME COLUMN "行政组织类型" TO org_type;
ALTER TABLE "组织列表" RENAME COLUMN "上级行政组织" TO parent_org_name;
ALTER TABLE "组织列表" RENAME COLUMN "上级行政组织编码" TO parent_org_code;
ALTER TABLE "组织列表" RENAME COLUMN "成立日期" TO established_date;
ALTER TABLE "组织列表" RENAME COLUMN "所属公司" TO company_name;
ALTER TABLE "组织列表" RENAME COLUMN "业务状态" TO business_status;
ALTER TABLE "组织列表" RENAME COLUMN "行政组织层级" TO org_level;
ALTER TABLE "组织列表" RENAME COLUMN "行政组织职能" TO org_function;
ALTER TABLE "组织列表" RENAME COLUMN "所在城市" TO city_name;
ALTER TABLE "组织列表" RENAME COLUMN "工作地" TO work_location;
ALTER TABLE "组织列表" RENAME COLUMN "物理层级" TO physical_level;
ALTER TABLE "组织列表" RENAME COLUMN "待停用日期" TO pending_disable_date;
ALTER TABLE "组织列表" RENAME COLUMN "部门类型" TO department_type;
ALTER TABLE "组织列表" RENAME COLUMN "流程层级_名称" TO process_level_name;
ALTER TABLE "组织列表" RENAME COLUMN "部门子分类_编码" TO dept_subcategory_code;
ALTER TABLE "组织列表" RENAME COLUMN "部门子分类_名称" TO dept_subcategory_name;
ALTER TABLE "组织列表" RENAME COLUMN "部门分类_编码" TO dept_category_code;
ALTER TABLE "组织列表" RENAME COLUMN "部门分类_名称" TO dept_category_name;
ALTER TABLE "组织列表" RENAME COLUMN "创建时间" TO org_created_time;
ALTER TABLE "组织列表" RENAME COLUMN "组织长名称" TO org_full_name;
ALTER TABLE "组织列表" RENAME COLUMN "组织负责人" TO org_manager_name;
ALTER TABLE "组织列表" RENAME COLUMN "责任HR工号" TO hr_owner_employee_no;
ALTER TABLE "组织列表" RENAME COLUMN "责任HR姓名" TO hr_owner_name;
ALTER TABLE "组织列表" RENAME COLUMN "责任HR含下级组织" TO hr_owner_include_children_flag;
ALTER TABLE "组织列表" RENAME COLUMN "责任HR是否透出" TO hr_owner_exposed_flag;
ALTER TABLE "组织列表" RENAME COLUMN "来源根组织" TO source_root_org;
ALTER TABLE "组织列表" RENAME COLUMN "包含所有下级" TO include_all_children;
ALTER TABLE "组织列表" RENAME COLUMN "来源文件名" TO source_file_name;
ALTER TABLE "组织列表" RENAME COLUMN "导入批次号" TO import_batch_no;
ALTER TABLE "组织列表" RENAME COLUMN "记录创建时间" TO created_at;
ALTER TABLE "组织列表" RENAME COLUMN "记录更新时间" TO updated_at;

ALTER TABLE "城市所属战区" RENAME COLUMN "城市名称" TO city_name;
ALTER TABLE "城市所属战区" RENAME COLUMN "所属战区" TO war_zone;
ALTER TABLE "城市所属战区" RENAME COLUMN "记录创建时间" TO created_at;
ALTER TABLE "城市所属战区" RENAME COLUMN "记录更新时间" TO updated_at;

ALTER TABLE "组织属性查询" RENAME COLUMN "行政组织编码" TO org_code;
ALTER TABLE "组织属性查询" RENAME COLUMN "序号" TO row_no;
ALTER TABLE "组织属性查询" RENAME COLUMN "行政组织名称" TO org_name;
ALTER TABLE "组织属性查询" RENAME COLUMN "行政组织类型" TO org_type;
ALTER TABLE "组织属性查询" RENAME COLUMN "上级行政组织" TO parent_org_name;
ALTER TABLE "组织属性查询" RENAME COLUMN "上级行政组织编码" TO parent_org_code;
ALTER TABLE "组织属性查询" RENAME COLUMN "成立日期" TO established_date;
ALTER TABLE "组织属性查询" RENAME COLUMN "所属公司" TO company_name;
ALTER TABLE "组织属性查询" RENAME COLUMN "业务状态" TO business_status;
ALTER TABLE "组织属性查询" RENAME COLUMN "行政组织层级" TO org_level;
ALTER TABLE "组织属性查询" RENAME COLUMN "行政组织职能" TO org_function;
ALTER TABLE "组织属性查询" RENAME COLUMN "所在城市" TO city_name;
ALTER TABLE "组织属性查询" RENAME COLUMN "工作地" TO work_location;
ALTER TABLE "组织属性查询" RENAME COLUMN "物理层级" TO physical_level;
ALTER TABLE "组织属性查询" RENAME COLUMN "待停用日期" TO pending_disable_date;
ALTER TABLE "组织属性查询" RENAME COLUMN "部门类型" TO department_type;
ALTER TABLE "组织属性查询" RENAME COLUMN "流程层级_名称" TO process_level_name;
ALTER TABLE "组织属性查询" RENAME COLUMN "组织流程层级判断" TO process_level_name_resolved;
ALTER TABLE "组织属性查询" RENAME COLUMN "组织流程层级分类" TO process_level_category;
ALTER TABLE "组织属性查询" RENAME COLUMN "部门子分类_编码" TO dept_subcategory_code;
ALTER TABLE "组织属性查询" RENAME COLUMN "部门子分类_名称" TO dept_subcategory_name;
ALTER TABLE "组织属性查询" RENAME COLUMN "部门分类_编码" TO dept_category_code;
ALTER TABLE "组织属性查询" RENAME COLUMN "部门分类_名称" TO dept_category_name;
ALTER TABLE "组织属性查询" RENAME COLUMN "创建时间" TO org_created_time;
ALTER TABLE "组织属性查询" RENAME COLUMN "组织长名称" TO org_full_name;
ALTER TABLE "组织属性查询" RENAME COLUMN "组织单位" TO org_unit_name;
ALTER TABLE "组织属性查询" RENAME COLUMN "组织单位命中规则" TO org_unit_rule;
ALTER TABLE "组织属性查询" RENAME COLUMN "组织授权级别" TO org_auth_level;
ALTER TABLE "组织属性查询" RENAME COLUMN "组织授权级别命中规则" TO org_auth_level_rule;
ALTER TABLE "组织属性查询" RENAME COLUMN "万御城市营业部" TO wanyu_city_sales_department;
ALTER TABLE "组织属性查询" RENAME COLUMN "所属战区" TO war_zone;
ALTER TABLE "组织属性查询" RENAME COLUMN "来源导入批次号" TO source_import_batch_no;
ALTER TABLE "组织属性查询" RENAME COLUMN "刷新时间" TO refreshed_at;
ALTER TABLE "组织属性查询" RENAME COLUMN "记录创建时间" TO created_at;
ALTER TABLE "组织属性查询" RENAME COLUMN "记录更新时间" TO updated_at;

ALTER TABLE "权限列表" RENAME COLUMN "角色编码" TO role_code;
ALTER TABLE "权限列表" RENAME COLUMN "角色名称" TO role_name;
ALTER TABLE "权限列表" RENAME COLUMN "权限级别" TO permission_level;
ALTER TABLE "权限列表" RENAME COLUMN "数据来源" TO source_system;
ALTER TABLE "权限列表" RENAME COLUMN "原始快照" TO raw_payload;
ALTER TABLE "权限列表" RENAME COLUMN "记录创建时间" TO created_at;
ALTER TABLE "权限列表" RENAME COLUMN "记录更新时间" TO updated_at;

CREATE OR REPLACE FUNCTION refresh_组织属性查询()
RETURNS VOID
LANGUAGE plpgsql
AS $$
BEGIN
    EXECUTE 'DROP TABLE IF EXISTS "组织属性查询__staging"';
    EXECUTE '
        CREATE TABLE "组织属性查询__staging" (
            org_code TEXT NOT NULL,
            row_no INTEGER,
            org_name TEXT,
            org_type TEXT,
            parent_org_name TEXT,
            parent_org_code TEXT,
            established_date TEXT,
            company_name TEXT,
            business_status TEXT,
            org_level TEXT,
            org_function TEXT,
            city_name TEXT,
            work_location TEXT,
            physical_level TEXT,
            pending_disable_date TEXT,
            department_type TEXT,
            process_level_name TEXT,
            process_level_name_resolved TEXT,
            process_level_category TEXT,
            dept_subcategory_code TEXT,
            dept_subcategory_name TEXT,
            dept_category_code TEXT,
            dept_category_name TEXT,
            org_created_time TEXT,
            org_full_name TEXT,
            org_unit_name TEXT,
            org_unit_rule TEXT,
            org_auth_level TEXT,
            org_auth_level_rule TEXT,
            wanyu_city_sales_department TEXT,
            war_zone TEXT,
            source_import_batch_no TEXT,
            refreshed_at TIMESTAMPTZ NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )';

    EXECUTE $INSERT$
        INSERT INTO "组织属性查询__staging" (
            org_code,
            row_no,
            org_name,
            org_type,
            parent_org_name,
            parent_org_code,
            established_date,
            company_name,
            business_status,
            org_level,
            org_function,
            city_name,
            work_location,
            physical_level,
            pending_disable_date,
            department_type,
            process_level_name,
            process_level_name_resolved,
            process_level_category,
            dept_subcategory_code,
            dept_subcategory_name,
            dept_category_code,
            dept_category_name,
            org_created_time,
            org_full_name,
            org_unit_name,
            org_unit_rule,
            org_auth_level,
            org_auth_level_rule,
            wanyu_city_sales_department,
            war_zone,
            source_import_batch_no,
            refreshed_at,
            created_at,
            updated_at
        )
        WITH RECURSIVE process_level_chain AS (
            SELECT
                o.org_code AS root_org_code,
                o.parent_org_code AS next_parent_org_code,
                NULLIF(BTRIM(o.process_level_name), '') AS candidate_process_level_name,
                0 AS depth,
                ARRAY[o.org_code] AS visited_org_codes
            FROM "组织列表" o

            UNION ALL

            SELECT
                plc.root_org_code,
                p.parent_org_code AS next_parent_org_code,
                NULLIF(BTRIM(p.process_level_name), '') AS candidate_process_level_name,
                plc.depth + 1 AS depth,
                plc.visited_org_codes || p.org_code AS visited_org_codes
            FROM process_level_chain plc
            JOIN "组织列表" p
              ON plc.next_parent_org_code = p.org_code
            WHERE plc.candidate_process_level_name IS NULL
              AND NOT (p.org_code = ANY(plc.visited_org_codes))
        ),
        resolved_process_level AS (
            SELECT DISTINCT ON (root_org_code)
                root_org_code AS org_code,
                candidate_process_level_name AS process_level_name_resolved
            FROM process_level_chain
            WHERE candidate_process_level_name IS NOT NULL
            ORDER BY root_org_code, depth
        )
        SELECT
            o.org_code,
            o.row_no,
            o.org_name,
            o.org_type,
            o.parent_org_name,
            o.parent_org_code,
            o.established_date,
            o.company_name,
            o.business_status,
            o.org_level,
            o.org_function,
            o.city_name,
            o.work_location,
            o.physical_level,
            o.pending_disable_date,
            o.department_type,
            o.process_level_name,
            COALESCE(fn_map_process_level_name_override(o.org_full_name), rpl.process_level_name_resolved),
            fn_map_process_level_category(
                COALESCE(fn_map_process_level_name_override(o.org_full_name), rpl.process_level_name_resolved),
                o.company_name,
                o.org_full_name
            ),
            o.dept_subcategory_code,
            o.dept_subcategory_name,
            o.dept_category_code,
            o.dept_category_name,
            o.org_created_time,
            o.org_full_name,
            fn_map_org_unit_name(o.org_full_name),
            fn_map_org_unit_rule(o.org_full_name),
            fn_map_org_auth_level(
                o.org_code,
                o.org_level,
                o.physical_level,
                o.org_full_name,
                fn_map_org_unit_name(o.org_full_name),
                fn_map_process_level_category(
                    COALESCE(fn_map_process_level_name_override(o.org_full_name), rpl.process_level_name_resolved),
                    o.company_name,
                    o.org_full_name
                )
            ),
            fn_map_org_auth_level_rule(
                o.org_code,
                o.org_level,
                o.physical_level,
                o.org_full_name,
                fn_map_org_unit_name(o.org_full_name),
                fn_map_process_level_category(
                    COALESCE(fn_map_process_level_name_override(o.org_full_name), rpl.process_level_name_resolved),
                    o.company_name,
                    o.org_full_name
                )
            ),
            fn_map_wanyu_city_sales_department(o.org_full_name),
            z.war_zone,
            o.import_batch_no,
            NOW(),
            NOW(),
            NOW()
        FROM "组织列表" o
        LEFT JOIN resolved_process_level rpl
            ON o.org_code = rpl.org_code
        LEFT JOIN "城市所属战区" z
            ON o.city_name = z.city_name
    $INSERT$;

    EXECUTE 'ANALYZE "组织属性查询__staging"';

    LOCK TABLE "组织属性查询" IN ACCESS EXCLUSIVE MODE;
    EXECUTE 'DROP TABLE IF EXISTS "组织属性查询__old"';
    EXECUTE 'ALTER TABLE "组织属性查询" RENAME TO "组织属性查询__old"';
    EXECUTE 'ALTER TABLE "组织属性查询__staging" RENAME TO "组织属性查询"';
    EXECUTE 'DROP TABLE "组织属性查询__old"';

    EXECUTE 'ALTER TABLE "组织属性查询" ADD CONSTRAINT "组织属性查询_pkey" PRIMARY KEY (org_code)';
    EXECUTE 'CREATE INDEX idx_组织属性查询_org_name ON "组织属性查询" (org_name)';
    EXECUTE 'CREATE INDEX idx_组织属性查询_parent_org_code ON "组织属性查询" (parent_org_code)';
    EXECUTE 'CREATE INDEX idx_组织属性查询_company_name ON "组织属性查询" (company_name)';
    EXECUTE 'CREATE INDEX idx_组织属性查询_org_level ON "组织属性查询" (org_level)';
    EXECUTE 'CREATE INDEX idx_组织属性查询_city_name ON "组织属性查询" (city_name)';
    EXECUTE 'CREATE INDEX idx_组织属性查询_process_level_category ON "组织属性查询" (process_level_category)';
    EXECUTE 'CREATE INDEX idx_组织属性查询_dept_category_code ON "组织属性查询" (dept_category_code)';
    EXECUTE 'CREATE INDEX idx_组织属性查询_dept_subcategory_code ON "组织属性查询" (dept_subcategory_code)';
    EXECUTE 'CREATE INDEX idx_组织属性查询_org_unit_name ON "组织属性查询" (org_unit_name)';
    EXECUTE 'CREATE INDEX idx_组织属性查询_org_auth_level ON "组织属性查询" (org_auth_level)';
    EXECUTE 'CREATE INDEX idx_组织属性查询_wanyu_city_sales_department ON "组织属性查询" (wanyu_city_sales_department)';
    EXECUTE 'CREATE INDEX idx_组织属性查询_war_zone ON "组织属性查询" (war_zone)';
    EXECUTE 'CREATE INDEX idx_组织属性查询_war_zone_city_name ON "组织属性查询" (war_zone, city_name)';
    EXECUTE 'CREATE INDEX idx_组织属性查询_org_unit_name_company_name ON "组织属性查询" (org_unit_name, company_name)';
    EXECUTE 'ANALYZE "组织属性查询"';
END;
$$;

COMMIT;
