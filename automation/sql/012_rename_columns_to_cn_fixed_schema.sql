-- 方案011B：固定字段中文化物理改列（前向）
-- 说明：
-- 1. 本脚本仅覆盖仓库已固化的固定字段，不覆盖 "组织列表" 运行期动态扩展列。
-- 2. 本脚本执行后，应用代码尚未完成中文列名切换前，不应直接发布到生产使用。
-- 3. 本脚本同时重建 refresh_组织属性查询()，否则组织属性查询刷新链路会失效。

BEGIN;

ALTER TABLE "申请单基本信息" RENAME COLUMN document_no TO "单据编号";
ALTER TABLE "申请单基本信息" RENAME COLUMN employee_no TO "工号";
ALTER TABLE "申请单基本信息" RENAME COLUMN permission_target TO "权限对象";
ALTER TABLE "申请单基本信息" RENAME COLUMN apply_reason TO "申请理由";
ALTER TABLE "申请单基本信息" RENAME COLUMN document_status TO "单据状态";
ALTER TABLE "申请单基本信息" RENAME COLUMN hr_org TO "人事管理组织";
ALTER TABLE "申请单基本信息" RENAME COLUMN company_name TO "公司";
ALTER TABLE "申请单基本信息" RENAME COLUMN department_name TO "部门";
ALTER TABLE "申请单基本信息" RENAME COLUMN position_name TO "职位";
ALTER TABLE "申请单基本信息" RENAME COLUMN apply_time TO "申请日期";
ALTER TABLE "申请单基本信息" RENAME COLUMN created_at TO "记录创建时间";
ALTER TABLE "申请单基本信息" RENAME COLUMN updated_at TO "记录更新时间";

ALTER TABLE "申请单权限列表" RENAME COLUMN id TO "权限明细ID";
ALTER TABLE "申请单权限列表" RENAME COLUMN document_no TO "单据编号";
ALTER TABLE "申请单权限列表" RENAME COLUMN line_no TO "明细行号";
ALTER TABLE "申请单权限列表" RENAME COLUMN apply_type TO "申请类型";
ALTER TABLE "申请单权限列表" RENAME COLUMN role_name TO "角色名称";
ALTER TABLE "申请单权限列表" RENAME COLUMN role_desc TO "角色描述";
ALTER TABLE "申请单权限列表" RENAME COLUMN role_code TO "角色编码";
ALTER TABLE "申请单权限列表" RENAME COLUMN social_security_unit TO "参保单位";
ALTER TABLE "申请单权限列表" RENAME COLUMN org_scope_count TO "组织范围数量";
ALTER TABLE "申请单权限列表" RENAME COLUMN created_at TO "记录创建时间";
ALTER TABLE "申请单权限列表" RENAME COLUMN updated_at TO "记录更新时间";

ALTER TABLE "申请单审批记录" RENAME COLUMN id TO "审批记录ID";
ALTER TABLE "申请单审批记录" RENAME COLUMN document_no TO "单据编号";
ALTER TABLE "申请单审批记录" RENAME COLUMN record_seq TO "审批记录顺序号";
ALTER TABLE "申请单审批记录" RENAME COLUMN node_name TO "节点名称";
ALTER TABLE "申请单审批记录" RENAME COLUMN approver_name TO "审批人";
ALTER TABLE "申请单审批记录" RENAME COLUMN approver_org_or_position TO "审批人组织或职位";
ALTER TABLE "申请单审批记录" RENAME COLUMN approval_action TO "审批动作";
ALTER TABLE "申请单审批记录" RENAME COLUMN approval_opinion TO "审批意见";
ALTER TABLE "申请单审批记录" RENAME COLUMN approval_time TO "审批时间";
ALTER TABLE "申请单审批记录" RENAME COLUMN raw_text TO "原始展示文本";
ALTER TABLE "申请单审批记录" RENAME COLUMN created_at TO "记录创建时间";

ALTER TABLE "申请表组织范围" RENAME COLUMN id TO "组织范围ID";
ALTER TABLE "申请表组织范围" RENAME COLUMN document_no TO "单据编号";
ALTER TABLE "申请表组织范围" RENAME COLUMN org_code TO "组织编码";
ALTER TABLE "申请表组织范围" RENAME COLUMN created_at TO "记录创建时间";

ALTER TABLE "在职花名册表" RENAME COLUMN employee_no TO "人员编号";
ALTER TABLE "在职花名册表" RENAME COLUMN query_date TO "查询日期";
ALTER TABLE "在职花名册表" RENAME COLUMN serial_no TO "序号";
ALTER TABLE "在职花名册表" RENAME COLUMN company_name TO "公司";
ALTER TABLE "在职花名册表" RENAME COLUMN company_id TO "公司ID";
ALTER TABLE "在职花名册表" RENAME COLUMN department_name TO "部门";
ALTER TABLE "在职花名册表" RENAME COLUMN department_long_text TO "部门长文本";
ALTER TABLE "在职花名册表" RENAME COLUMN department_id TO "部门ID";
ALTER TABLE "在职花名册表" RENAME COLUMN department_city TO "部门所属城市";
ALTER TABLE "在职花名册表" RENAME COLUMN employee_name TO "姓名";
ALTER TABLE "在职花名册表" RENAME COLUMN position_code TO "职位编码";
ALTER TABLE "在职花名册表" RENAME COLUMN position_name TO "职位名称";
ALTER TABLE "在职花名册表" RENAME COLUMN specific_post_name TO "具体岗位_新";
ALTER TABLE "在职花名册表" RENAME COLUMN critical_post_flag TO "是否关键岗位";
ALTER TABLE "在职花名册表" RENAME COLUMN post_family TO "岗位族";
ALTER TABLE "在职花名册表" RENAME COLUMN job_title TO "职务";
ALTER TABLE "在职花名册表" RENAME COLUMN level1_function_name TO "一级职能名称";
ALTER TABLE "在职花名册表" RENAME COLUMN level2_function_name TO "二级职能名称";
ALTER TABLE "在职花名册表" RENAME COLUMN standard_position_code TO "标准岗位编码";
ALTER TABLE "在职花名册表" RENAME COLUMN standard_position_name TO "标准岗位名称";
ALTER TABLE "在职花名册表" RENAME COLUMN superior_code TO "上级编码";
ALTER TABLE "在职花名册表" RENAME COLUMN superior_name TO "上级名称";
ALTER TABLE "在职花名册表" RENAME COLUMN hr_partner_employee_no TO "对接HR工号";
ALTER TABLE "在职花名册表" RENAME COLUMN hr_partner_name TO "对接HR姓名";
ALTER TABLE "在职花名册表" RENAME COLUMN team_leader_name TO "班长";
ALTER TABLE "在职花名册表" RENAME COLUMN employee_group TO "员工组";
ALTER TABLE "在职花名册表" RENAME COLUMN employee_subgroup TO "员工子组";
ALTER TABLE "在职花名册表" RENAME COLUMN sub_label TO "子标签";
ALTER TABLE "在职花名册表" RENAME COLUMN entry_date TO "入职日期";
ALTER TABLE "在职花名册表" RENAME COLUMN company_seniority_text TO "司龄";
ALTER TABLE "在职花名册表" RENAME COLUMN gender TO "性别";
ALTER TABLE "在职花名册表" RENAME COLUMN birth_date TO "出生日期";
ALTER TABLE "在职花名册表" RENAME COLUMN birthday_type TO "生日类型";
ALTER TABLE "在职花名册表" RENAME COLUMN actual_birthday TO "实际生日";
ALTER TABLE "在职花名册表" RENAME COLUMN age_text TO "年龄";
ALTER TABLE "在职花名册表" RENAME COLUMN household_registration_province TO "户口所在省";
ALTER TABLE "在职花名册表" RENAME COLUMN household_registration_city TO "户口所在市";
ALTER TABLE "在职花名册表" RENAME COLUMN registered_residence TO "户籍地";
ALTER TABLE "在职花名册表" RENAME COLUMN social_security_location TO "参保地";
ALTER TABLE "在职花名册表" RENAME COLUMN marital_status TO "婚姻状况";
ALTER TABLE "在职花名册表" RENAME COLUMN education_level TO "学历";
ALTER TABLE "在职花名册表" RENAME COLUMN study_mode TO "学习形式";
ALTER TABLE "在职花名册表" RENAME COLUMN graduation_date TO "毕业时间";
ALTER TABLE "在职花名册表" RENAME COLUMN degree TO "学位";
ALTER TABLE "在职花名册表" RENAME COLUMN school_name TO "学校";
ALTER TABLE "在职花名册表" RENAME COLUMN alternate_school_name TO "其他院校";
ALTER TABLE "在职花名册表" RENAME COLUMN major_name TO "院校专业";
ALTER TABLE "在职花名册表" RENAME COLUMN id_number TO "证件号码";
ALTER TABLE "在职花名册表" RENAME COLUMN phone_number TO "联系电话";
ALTER TABLE "在职花名册表" RENAME COLUMN vanke_email TO "万科邮箱";
ALTER TABLE "在职花名册表" RENAME COLUMN onewo_email TO "万物云邮箱";
ALTER TABLE "在职花名册表" RENAME COLUMN domain_account TO "域账号";
ALTER TABLE "在职花名册表" RENAME COLUMN employment_status TO "雇佣状态";
ALTER TABLE "在职花名册表" RENAME COLUMN department_category TO "部门分类";
ALTER TABLE "在职花名册表" RENAME COLUMN department_subcategory TO "部门子分类";
ALTER TABLE "在职花名册表" RENAME COLUMN external_roster_flag TO "是否外盘人员";
ALTER TABLE "在职花名册表" RENAME COLUMN contract_type TO "合同类型";
ALTER TABLE "在职花名册表" RENAME COLUMN contract_signing_entity TO "合同签订主体";
ALTER TABLE "在职花名册表" RENAME COLUMN contract_start_date TO "合同开始日期";
ALTER TABLE "在职花名册表" RENAME COLUMN contract_end_date TO "合同结束日期";
ALTER TABLE "在职花名册表" RENAME COLUMN start_work_date TO "参加工作时间";
ALTER TABLE "在职花名册表" RENAME COLUMN service_start_date_at_vanke TO "服务万科时间";
ALTER TABLE "在职花名册表" RENAME COLUMN latest_entry_date_to_vanke TO "最新入职万科日期";
ALTER TABLE "在职花名册表" RENAME COLUMN seniority_start_date TO "司龄起算时间";
ALTER TABLE "在职花名册表" RENAME COLUMN working_years_text TO "工龄";
ALTER TABLE "在职花名册表" RENAME COLUMN trainee_type TO "储备见习类型";
ALTER TABLE "在职花名册表" RENAME COLUMN trainee_start_date TO "储备见习开始日期";
ALTER TABLE "在职花名册表" RENAME COLUMN trainee_end_date TO "储备见习结束日期";
ALTER TABLE "在职花名册表" RENAME COLUMN trainee_post_name TO "储备岗位名称";
ALTER TABLE "在职花名册表" RENAME COLUMN post_remark_property TO "岗位备注_物业";
ALTER TABLE "在职花名册表" RENAME COLUMN sequence_attribute TO "序列属性";
ALTER TABLE "在职花名册表" RENAME COLUMN sequence_type TO "序列类型";
ALTER TABLE "在职花名册表" RENAME COLUMN org_path_id TO "组织路径ID";
ALTER TABLE "在职花名册表" RENAME COLUMN org_path_name TO "组织路径名称";
ALTER TABLE "在职花名册表" RENAME COLUMN contract_term TO "合同期限";
ALTER TABLE "在职花名册表" RENAME COLUMN military_service_flag TO "是否服过兵役";
ALTER TABLE "在职花名册表" RENAME COLUMN discharge_certificate_no TO "退役证编号";
ALTER TABLE "在职花名册表" RENAME COLUMN discharge_certificate_type TO "退伍证类型";
ALTER TABLE "在职花名册表" RENAME COLUMN enlistment_date TO "入伍时间";
ALTER TABLE "在职花名册表" RENAME COLUMN discharge_date TO "退役时间";
ALTER TABLE "在职花名册表" RENAME COLUMN leadership_category TO "领导力类别";
ALTER TABLE "在职花名册表" RENAME COLUMN id_document_permanent_flag TO "证件是否永久有效";
ALTER TABLE "在职花名册表" RENAME COLUMN id_document_valid_from TO "证件有效期起";
ALTER TABLE "在职花名册表" RENAME COLUMN id_document_valid_to TO "证件有效期止";
ALTER TABLE "在职花名册表" RENAME COLUMN primary_position_flag TO "是否主任职";
ALTER TABLE "在职花名册表" RENAME COLUMN employment_type TO "任职类型";
ALTER TABLE "在职花名册表" RENAME COLUMN ethnicity TO "民族";
ALTER TABLE "在职花名册表" RENAME COLUMN household_registration_type TO "户口性质";
ALTER TABLE "在职花名册表" RENAME COLUMN household_registration_location TO "户口所在地";
ALTER TABLE "在职花名册表" RENAME COLUMN birthplace TO "出生地";
ALTER TABLE "在职花名册表" RENAME COLUMN native_place TO "籍贯";
ALTER TABLE "在职花名册表" RENAME COLUMN nationality TO "国籍";
ALTER TABLE "在职花名册表" RENAME COLUMN birth_country TO "出生国家";
ALTER TABLE "在职花名册表" RENAME COLUMN birthplace_province TO "出生地所在省";
ALTER TABLE "在职花名册表" RENAME COLUMN birthplace_city TO "出生地所在市";
ALTER TABLE "在职花名册表" RENAME COLUMN campus_recruitment_cohort TO "校招届别";
ALTER TABLE "在职花名册表" RENAME COLUMN political_status TO "政治面貌";
ALTER TABLE "在职花名册表" RENAME COLUMN party_organization_name TO "所属党组织全称";
ALTER TABLE "在职花名册表" RENAME COLUMN party_member_status TO "党员状态";
ALTER TABLE "在职花名册表" RENAME COLUMN source_file_name TO "来源文件名";
ALTER TABLE "在职花名册表" RENAME COLUMN import_batch_no TO "导入批次号";
ALTER TABLE "在职花名册表" RENAME COLUMN row_no TO "导入行号";
ALTER TABLE "在职花名册表" RENAME COLUMN downloaded_at TO "下载时间";
ALTER TABLE "在职花名册表" RENAME COLUMN imported_at TO "导入时间";
ALTER TABLE "在职花名册表" RENAME COLUMN extra_columns_json TO "扩展字段JSON";
ALTER TABLE "在职花名册表" RENAME COLUMN created_at TO "记录创建时间";
ALTER TABLE "在职花名册表" RENAME COLUMN updated_at TO "记录更新时间";

ALTER TABLE "组织列表" RENAME COLUMN org_code TO "行政组织编码";
ALTER TABLE "组织列表" RENAME COLUMN row_no TO "序号";
ALTER TABLE "组织列表" RENAME COLUMN org_name TO "行政组织名称";
ALTER TABLE "组织列表" RENAME COLUMN org_type TO "行政组织类型";
ALTER TABLE "组织列表" RENAME COLUMN parent_org_name TO "上级行政组织";
ALTER TABLE "组织列表" RENAME COLUMN parent_org_code TO "上级行政组织编码";
ALTER TABLE "组织列表" RENAME COLUMN established_date TO "成立日期";
ALTER TABLE "组织列表" RENAME COLUMN company_name TO "所属公司";
ALTER TABLE "组织列表" RENAME COLUMN business_status TO "业务状态";
ALTER TABLE "组织列表" RENAME COLUMN org_level TO "行政组织层级";
ALTER TABLE "组织列表" RENAME COLUMN org_function TO "行政组织职能";
ALTER TABLE "组织列表" RENAME COLUMN city_name TO "所在城市";
ALTER TABLE "组织列表" RENAME COLUMN work_location TO "工作地";
ALTER TABLE "组织列表" RENAME COLUMN physical_level TO "物理层级";
ALTER TABLE "组织列表" RENAME COLUMN pending_disable_date TO "待停用日期";
ALTER TABLE "组织列表" RENAME COLUMN department_type TO "部门类型";
ALTER TABLE "组织列表" RENAME COLUMN process_level_name TO "流程层级_名称";
ALTER TABLE "组织列表" RENAME COLUMN dept_subcategory_code TO "部门子分类_编码";
ALTER TABLE "组织列表" RENAME COLUMN dept_subcategory_name TO "部门子分类_名称";
ALTER TABLE "组织列表" RENAME COLUMN dept_category_code TO "部门分类_编码";
ALTER TABLE "组织列表" RENAME COLUMN dept_category_name TO "部门分类_名称";
ALTER TABLE "组织列表" RENAME COLUMN org_created_time TO "创建时间";
ALTER TABLE "组织列表" RENAME COLUMN org_full_name TO "组织长名称";
ALTER TABLE "组织列表" RENAME COLUMN org_manager_name TO "组织负责人";
ALTER TABLE "组织列表" RENAME COLUMN hr_owner_employee_no TO "责任HR工号";
ALTER TABLE "组织列表" RENAME COLUMN hr_owner_name TO "责任HR姓名";
ALTER TABLE "组织列表" RENAME COLUMN hr_owner_include_children_flag TO "责任HR含下级组织";
ALTER TABLE "组织列表" RENAME COLUMN hr_owner_exposed_flag TO "责任HR是否透出";
ALTER TABLE "组织列表" RENAME COLUMN source_root_org TO "来源根组织";
ALTER TABLE "组织列表" RENAME COLUMN include_all_children TO "包含所有下级";
ALTER TABLE "组织列表" RENAME COLUMN source_file_name TO "来源文件名";
ALTER TABLE "组织列表" RENAME COLUMN import_batch_no TO "导入批次号";
ALTER TABLE "组织列表" RENAME COLUMN created_at TO "记录创建时间";
ALTER TABLE "组织列表" RENAME COLUMN updated_at TO "记录更新时间";

ALTER TABLE "城市所属战区" RENAME COLUMN city_name TO "城市名称";
ALTER TABLE "城市所属战区" RENAME COLUMN war_zone TO "所属战区";
ALTER TABLE "城市所属战区" RENAME COLUMN created_at TO "记录创建时间";
ALTER TABLE "城市所属战区" RENAME COLUMN updated_at TO "记录更新时间";

ALTER TABLE "组织属性查询" RENAME COLUMN org_code TO "行政组织编码";
ALTER TABLE "组织属性查询" RENAME COLUMN row_no TO "序号";
ALTER TABLE "组织属性查询" RENAME COLUMN org_name TO "行政组织名称";
ALTER TABLE "组织属性查询" RENAME COLUMN org_type TO "行政组织类型";
ALTER TABLE "组织属性查询" RENAME COLUMN parent_org_name TO "上级行政组织";
ALTER TABLE "组织属性查询" RENAME COLUMN parent_org_code TO "上级行政组织编码";
ALTER TABLE "组织属性查询" RENAME COLUMN established_date TO "成立日期";
ALTER TABLE "组织属性查询" RENAME COLUMN company_name TO "所属公司";
ALTER TABLE "组织属性查询" RENAME COLUMN business_status TO "业务状态";
ALTER TABLE "组织属性查询" RENAME COLUMN org_level TO "行政组织层级";
ALTER TABLE "组织属性查询" RENAME COLUMN org_function TO "行政组织职能";
ALTER TABLE "组织属性查询" RENAME COLUMN city_name TO "所在城市";
ALTER TABLE "组织属性查询" RENAME COLUMN work_location TO "工作地";
ALTER TABLE "组织属性查询" RENAME COLUMN physical_level TO "物理层级";
ALTER TABLE "组织属性查询" RENAME COLUMN pending_disable_date TO "待停用日期";
ALTER TABLE "组织属性查询" RENAME COLUMN department_type TO "部门类型";
ALTER TABLE "组织属性查询" RENAME COLUMN process_level_name TO "流程层级_名称";
ALTER TABLE "组织属性查询" RENAME COLUMN process_level_name_resolved TO "组织流程层级判断";
ALTER TABLE "组织属性查询" RENAME COLUMN process_level_category TO "组织流程层级分类";
ALTER TABLE "组织属性查询" RENAME COLUMN dept_subcategory_code TO "部门子分类_编码";
ALTER TABLE "组织属性查询" RENAME COLUMN dept_subcategory_name TO "部门子分类_名称";
ALTER TABLE "组织属性查询" RENAME COLUMN dept_category_code TO "部门分类_编码";
ALTER TABLE "组织属性查询" RENAME COLUMN dept_category_name TO "部门分类_名称";
ALTER TABLE "组织属性查询" RENAME COLUMN org_created_time TO "创建时间";
ALTER TABLE "组织属性查询" RENAME COLUMN org_full_name TO "组织长名称";
ALTER TABLE "组织属性查询" RENAME COLUMN org_unit_name TO "组织单位";
ALTER TABLE "组织属性查询" RENAME COLUMN org_unit_rule TO "组织单位命中规则";
ALTER TABLE "组织属性查询" RENAME COLUMN org_auth_level TO "组织授权级别";
ALTER TABLE "组织属性查询" RENAME COLUMN org_auth_level_rule TO "组织授权级别命中规则";
ALTER TABLE "组织属性查询" RENAME COLUMN wanyu_city_sales_department TO "万御城市营业部";
ALTER TABLE "组织属性查询" RENAME COLUMN war_zone TO "所属战区";
ALTER TABLE "组织属性查询" RENAME COLUMN source_import_batch_no TO "来源导入批次号";
ALTER TABLE "组织属性查询" RENAME COLUMN refreshed_at TO "刷新时间";
ALTER TABLE "组织属性查询" RENAME COLUMN created_at TO "记录创建时间";
ALTER TABLE "组织属性查询" RENAME COLUMN updated_at TO "记录更新时间";

ALTER TABLE "权限列表" RENAME COLUMN role_code TO "角色编码";
ALTER TABLE "权限列表" RENAME COLUMN role_name TO "角色名称";
ALTER TABLE "权限列表" RENAME COLUMN permission_level TO "权限级别";
ALTER TABLE "权限列表" RENAME COLUMN source_system TO "数据来源";
ALTER TABLE "权限列表" RENAME COLUMN raw_payload TO "原始快照";
ALTER TABLE "权限列表" RENAME COLUMN created_at TO "记录创建时间";
ALTER TABLE "权限列表" RENAME COLUMN updated_at TO "记录更新时间";
ALTER TABLE "权限列表" DROP COLUMN IF EXISTS role_group;
ALTER TABLE "权限列表" DROP COLUMN IF EXISTS is_remote_role;
ALTER TABLE "权限列表" DROP COLUMN IF EXISTS is_deprecated;
ALTER TABLE "权限列表" DROP COLUMN IF EXISTS is_active;

CREATE OR REPLACE FUNCTION refresh_组织属性查询()
RETURNS VOID
LANGUAGE plpgsql
AS $$
BEGIN
    EXECUTE 'DROP TABLE IF EXISTS "组织属性查询__staging"';
    EXECUTE '
        CREATE TABLE "组织属性查询__staging" (
            "行政组织编码" TEXT NOT NULL,
            "序号" INTEGER,
            "行政组织名称" TEXT,
            "行政组织类型" TEXT,
            "上级行政组织" TEXT,
            "上级行政组织编码" TEXT,
            "成立日期" TEXT,
            "所属公司" TEXT,
            "业务状态" TEXT,
            "行政组织层级" TEXT,
            "行政组织职能" TEXT,
            "所在城市" TEXT,
            "工作地" TEXT,
            "物理层级" TEXT,
            "待停用日期" TEXT,
            "部门类型" TEXT,
            "流程层级_名称" TEXT,
            "组织流程层级判断" TEXT,
            "组织流程层级分类" TEXT,
            "部门子分类_编码" TEXT,
            "部门子分类_名称" TEXT,
            "部门分类_编码" TEXT,
            "部门分类_名称" TEXT,
            "创建时间" TEXT,
            "组织长名称" TEXT,
            "组织单位" TEXT,
            "组织单位命中规则" TEXT,
            "组织授权级别" TEXT,
            "组织授权级别命中规则" TEXT,
            "万御城市营业部" TEXT,
            "所属战区" TEXT,
            "来源导入批次号" TEXT,
            "刷新时间" TIMESTAMPTZ NOT NULL,
            "记录创建时间" TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            "记录更新时间" TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )';

    EXECUTE $INSERT$
        INSERT INTO "组织属性查询__staging" (
            "行政组织编码",
            "序号",
            "行政组织名称",
            "行政组织类型",
            "上级行政组织",
            "上级行政组织编码",
            "成立日期",
            "所属公司",
            "业务状态",
            "行政组织层级",
            "行政组织职能",
            "所在城市",
            "工作地",
            "物理层级",
            "待停用日期",
            "部门类型",
            "流程层级_名称",
            "组织流程层级判断",
            "组织流程层级分类",
            "部门子分类_编码",
            "部门子分类_名称",
            "部门分类_编码",
            "部门分类_名称",
            "创建时间",
            "组织长名称",
            "组织单位",
            "组织单位命中规则",
            "组织授权级别",
            "组织授权级别命中规则",
            "万御城市营业部",
            "所属战区",
            "来源导入批次号",
            "刷新时间",
            "记录创建时间",
            "记录更新时间"
        )
        WITH RECURSIVE process_level_chain AS (
            SELECT
                o."行政组织编码" AS root_org_code,
                o."上级行政组织编码" AS next_parent_org_code,
                NULLIF(BTRIM(o."流程层级_名称"), '') AS candidate_process_level_name,
                0 AS depth,
                ARRAY[o."行政组织编码"] AS visited_org_codes
            FROM "组织列表" o

            UNION ALL

            SELECT
                plc.root_org_code,
                p."上级行政组织编码" AS next_parent_org_code,
                NULLIF(BTRIM(p."流程层级_名称"), '') AS candidate_process_level_name,
                plc.depth + 1 AS depth,
                plc.visited_org_codes || p."行政组织编码" AS visited_org_codes
            FROM process_level_chain plc
            JOIN "组织列表" p
              ON plc.next_parent_org_code = p."行政组织编码"
            WHERE plc.candidate_process_level_name IS NULL
              AND NOT (p."行政组织编码" = ANY(plc.visited_org_codes))
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
            o."行政组织编码",
            o."序号",
            o."行政组织名称",
            o."行政组织类型",
            o."上级行政组织",
            o."上级行政组织编码",
            o."成立日期",
            o."所属公司",
            o."业务状态",
            o."行政组织层级",
            o."行政组织职能",
            o."所在城市",
            o."工作地",
            o."物理层级",
            o."待停用日期",
            o."部门类型",
            o."流程层级_名称",
            COALESCE(fn_map_process_level_name_override(o."组织长名称"), rpl.process_level_name_resolved),
            fn_map_process_level_category(
                COALESCE(fn_map_process_level_name_override(o."组织长名称"), rpl.process_level_name_resolved),
                o."所属公司",
                o."组织长名称"
            ),
            o."部门子分类_编码",
            o."部门子分类_名称",
            o."部门分类_编码",
            o."部门分类_名称",
            o."创建时间",
            o."组织长名称",
            fn_map_org_unit_name(o."组织长名称"),
            fn_map_org_unit_rule(o."组织长名称"),
            fn_map_org_auth_level(
                o."行政组织编码",
                o."行政组织层级",
                o."物理层级",
                o."组织长名称",
                fn_map_org_unit_name(o."组织长名称"),
                fn_map_process_level_category(
                    COALESCE(fn_map_process_level_name_override(o."组织长名称"), rpl.process_level_name_resolved),
                    o."所属公司",
                    o."组织长名称"
                )
            ),
            fn_map_org_auth_level_rule(
                o."行政组织编码",
                o."行政组织层级",
                o."物理层级",
                o."组织长名称",
                fn_map_org_unit_name(o."组织长名称"),
                fn_map_process_level_category(
                    COALESCE(fn_map_process_level_name_override(o."组织长名称"), rpl.process_level_name_resolved),
                    o."所属公司",
                    o."组织长名称"
                )
            ),
            fn_map_wanyu_city_sales_department(o."组织长名称"),
            z."所属战区",
            o."导入批次号",
            NOW(),
            NOW(),
            NOW()
        FROM "组织列表" o
        LEFT JOIN resolved_process_level rpl
            ON o."行政组织编码" = rpl.org_code
        LEFT JOIN "城市所属战区" z
            ON o."所在城市" = z."城市名称"
    $INSERT$;

    EXECUTE 'ANALYZE "组织属性查询__staging"';

    LOCK TABLE "组织属性查询" IN ACCESS EXCLUSIVE MODE;
    EXECUTE 'DROP TABLE IF EXISTS "组织属性查询__old"';
    EXECUTE 'ALTER TABLE "组织属性查询" RENAME TO "组织属性查询__old"';
    EXECUTE 'ALTER TABLE "组织属性查询__staging" RENAME TO "组织属性查询"';
    EXECUTE 'DROP TABLE "组织属性查询__old"';

    EXECUTE 'ALTER TABLE "组织属性查询" ADD CONSTRAINT "组织属性查询_pkey" PRIMARY KEY ("行政组织编码")';
    EXECUTE 'CREATE INDEX idx_组织属性查询_org_name ON "组织属性查询" ("行政组织名称")';
    EXECUTE 'CREATE INDEX idx_组织属性查询_parent_org_code ON "组织属性查询" ("上级行政组织编码")';
    EXECUTE 'CREATE INDEX idx_组织属性查询_company_name ON "组织属性查询" ("所属公司")';
    EXECUTE 'CREATE INDEX idx_组织属性查询_org_level ON "组织属性查询" ("行政组织层级")';
    EXECUTE 'CREATE INDEX idx_组织属性查询_city_name ON "组织属性查询" ("所在城市")';
    EXECUTE 'CREATE INDEX idx_组织属性查询_process_level_category ON "组织属性查询" ("组织流程层级分类")';
    EXECUTE 'CREATE INDEX idx_组织属性查询_dept_category_code ON "组织属性查询" ("部门分类_编码")';
    EXECUTE 'CREATE INDEX idx_组织属性查询_dept_subcategory_code ON "组织属性查询" ("部门子分类_编码")';
    EXECUTE 'CREATE INDEX idx_组织属性查询_org_unit_name ON "组织属性查询" ("组织单位")';
    EXECUTE 'CREATE INDEX idx_组织属性查询_org_auth_level ON "组织属性查询" ("组织授权级别")';
    EXECUTE 'CREATE INDEX idx_组织属性查询_wanyu_city_sales_department ON "组织属性查询" ("万御城市营业部")';
    EXECUTE 'CREATE INDEX idx_组织属性查询_war_zone ON "组织属性查询" ("所属战区")';
    EXECUTE 'CREATE INDEX idx_组织属性查询_war_zone_city_name ON "组织属性查询" ("所属战区", "所在城市")';
    EXECUTE 'CREATE INDEX idx_组织属性查询_org_unit_name_company_name ON "组织属性查询" ("组织单位", "所属公司")';
    EXECUTE 'ANALYZE "组织属性查询"';
END;
$$;

COMMIT;
