CREATE TABLE IF NOT EXISTS "在职花名册表" (
    employee_no TEXT PRIMARY KEY,
    query_date DATE NOT NULL,
    serial_no TEXT,
    company_name TEXT,
    company_id TEXT,
    department_name TEXT,
    department_long_text TEXT,
    department_id TEXT,
    department_city TEXT,
    employee_name TEXT,
    position_code TEXT,
    position_name TEXT,
    specific_post_name TEXT,
    critical_post_flag TEXT,
    post_family TEXT,
    job_title TEXT,
    level1_function_name TEXT,
    level2_function_name TEXT,
    standard_position_code TEXT,
    standard_position_name TEXT,
    superior_code TEXT,
    superior_name TEXT,
    hr_partner_employee_no TEXT,
    hr_partner_name TEXT,
    team_leader_name TEXT,
    employee_group TEXT,
    employee_subgroup TEXT,
    sub_label TEXT,
    entry_date DATE,
    company_seniority_text TEXT,
    gender TEXT,
    birth_date DATE,
    birthday_type TEXT,
    actual_birthday TEXT,
    age_text TEXT,
    household_registration_province TEXT,
    household_registration_city TEXT,
    registered_residence TEXT,
    social_security_location TEXT,
    marital_status TEXT,
    education_level TEXT,
    study_mode TEXT,
    graduation_date DATE,
    degree TEXT,
    school_name TEXT,
    alternate_school_name TEXT,
    major_name TEXT,
    id_number TEXT,
    phone_number TEXT,
    vanke_email TEXT,
    onewo_email TEXT,
    domain_account TEXT,
    employment_status TEXT,
    department_category TEXT,
    department_subcategory TEXT,
    external_roster_flag TEXT,
    contract_type TEXT,
    contract_signing_entity TEXT,
    contract_start_date DATE,
    contract_end_date DATE,
    start_work_date DATE,
    service_start_date_at_vanke DATE,
    latest_entry_date_to_vanke DATE,
    seniority_start_date DATE,
    working_years_text TEXT,
    trainee_type TEXT,
    trainee_start_date DATE,
    trainee_end_date DATE,
    trainee_post_name TEXT,
    post_remark_property TEXT,
    sequence_attribute TEXT,
    sequence_type TEXT,
    org_path_id TEXT,
    org_path_name TEXT,
    contract_term TEXT,
    military_service_flag TEXT,
    discharge_certificate_no TEXT,
    discharge_certificate_type TEXT,
    enlistment_date DATE,
    discharge_date DATE,
    leadership_category TEXT,
    id_document_permanent_flag TEXT,
    id_document_valid_from DATE,
    id_document_valid_to DATE,
    primary_position_flag TEXT,
    employment_type TEXT,
    ethnicity TEXT,
    household_registration_type TEXT,
    household_registration_location TEXT,
    birthplace TEXT,
    native_place TEXT,
    nationality TEXT,
    birth_country TEXT,
    birthplace_province TEXT,
    birthplace_city TEXT,
    campus_recruitment_cohort TEXT,
    political_status TEXT,
    party_organization_name TEXT,
    party_member_status TEXT,
    source_file_name TEXT NOT NULL,
    import_batch_no TEXT NOT NULL,
    row_no INTEGER,
    downloaded_at TIMESTAMP NULL,
    imported_at TIMESTAMP NOT NULL DEFAULT NOW(),
    extra_columns_json JSONB NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS employee_no TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS query_date DATE;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS serial_no TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS company_name TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS company_id TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS department_name TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS department_long_text TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS department_id TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS department_city TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS employee_name TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS position_code TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS position_name TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS specific_post_name TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS critical_post_flag TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS post_family TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS job_title TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS level1_function_name TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS level2_function_name TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS standard_position_code TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS standard_position_name TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS superior_code TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS superior_name TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS hr_partner_employee_no TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS hr_partner_name TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS team_leader_name TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS employee_group TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS employee_subgroup TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS sub_label TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS entry_date DATE;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS company_seniority_text TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS gender TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS birth_date DATE;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS birthday_type TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS actual_birthday TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS age_text TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS household_registration_province TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS household_registration_city TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS registered_residence TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS social_security_location TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS marital_status TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS education_level TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS study_mode TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS graduation_date DATE;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS degree TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS school_name TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS alternate_school_name TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS major_name TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS id_number TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS phone_number TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS vanke_email TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS onewo_email TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS domain_account TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS employment_status TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS department_category TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS department_subcategory TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS external_roster_flag TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS contract_type TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS contract_signing_entity TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS contract_start_date DATE;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS contract_end_date DATE;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS start_work_date DATE;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS service_start_date_at_vanke DATE;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS latest_entry_date_to_vanke DATE;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS seniority_start_date DATE;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS working_years_text TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS trainee_type TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS trainee_start_date DATE;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS trainee_end_date DATE;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS trainee_post_name TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS post_remark_property TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS sequence_attribute TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS sequence_type TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS org_path_id TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS org_path_name TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS contract_term TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS military_service_flag TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS discharge_certificate_no TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS discharge_certificate_type TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS enlistment_date DATE;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS discharge_date DATE;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS leadership_category TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS id_document_permanent_flag TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS id_document_valid_from DATE;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS id_document_valid_to DATE;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS primary_position_flag TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS employment_type TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS ethnicity TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS household_registration_type TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS household_registration_location TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS birthplace TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS native_place TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS nationality TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS birth_country TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS birthplace_province TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS birthplace_city TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS campus_recruitment_cohort TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS political_status TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS party_organization_name TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS party_member_status TEXT;
ALTER TABLE "在职花名册表" ALTER COLUMN actual_birthday TYPE TEXT USING actual_birthday::text;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS source_file_name TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS import_batch_no TEXT;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS row_no INTEGER;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS downloaded_at TIMESTAMP NULL;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS imported_at TIMESTAMP NOT NULL DEFAULT NOW();
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS extra_columns_json JSONB NULL;
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS created_at TIMESTAMP NOT NULL DEFAULT NOW();
ALTER TABLE "在职花名册表" ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NOT NULL DEFAULT NOW();

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = '在职花名册表'
          AND column_name = 'raw_row_json'
    ) THEN
        UPDATE "在职花名册表"
        SET
            serial_no = COALESCE(serial_no, NULLIF(raw_row_json->>'序号', '')),
            company_name = COALESCE(company_name, NULLIF(raw_row_json->>'公司', '')),
            company_id = COALESCE(company_id, NULLIF(raw_row_json->>'公司ID', '')),
            department_name = COALESCE(department_name, NULLIF(raw_row_json->>'部门', '')),
            department_long_text = COALESCE(department_long_text, NULLIF(raw_row_json->>'部门长文本', '')),
            department_id = COALESCE(department_id, NULLIF(raw_row_json->>'部门ID', '')),
            department_city = COALESCE(department_city, NULLIF(raw_row_json->>'部门所属城市', '')),
            employee_no = COALESCE(employee_no, NULLIF(raw_row_json->>'人员编号', '')),
            employee_name = COALESCE(employee_name, NULLIF(raw_row_json->>'姓名', '')),
            position_code = COALESCE(position_code, NULLIF(raw_row_json->>'职位编码', '')),
            position_name = COALESCE(position_name, NULLIF(raw_row_json->>'职位名称', '')),
            specific_post_name = COALESCE(specific_post_name, NULLIF(raw_row_json->>'具体岗位(新)', ''), NULLIF(raw_row_json->>'具体岗位（新）', '')),
            critical_post_flag = COALESCE(critical_post_flag, NULLIF(raw_row_json->>'是否关键岗位', '')),
            post_family = COALESCE(post_family, NULLIF(raw_row_json->>'岗位族', '')),
            job_title = COALESCE(job_title, NULLIF(raw_row_json->>'职务', '')),
            level1_function_name = COALESCE(level1_function_name, NULLIF(raw_row_json->>'一级职能名称', '')),
            level2_function_name = COALESCE(level2_function_name, NULLIF(raw_row_json->>'二级职能名称', '')),
            standard_position_code = COALESCE(standard_position_code, NULLIF(raw_row_json->>'标准岗位编码', '')),
            standard_position_name = COALESCE(standard_position_name, NULLIF(raw_row_json->>'标准岗位名称', '')),
            superior_code = COALESCE(superior_code, NULLIF(raw_row_json->>'上级编码', '')),
            superior_name = COALESCE(superior_name, NULLIF(raw_row_json->>'上级名称', '')),
            hr_partner_employee_no = COALESCE(hr_partner_employee_no, NULLIF(raw_row_json->>'对接HR工号', '')),
            hr_partner_name = COALESCE(hr_partner_name, NULLIF(raw_row_json->>'对接HR姓名', '')),
            team_leader_name = COALESCE(team_leader_name, NULLIF(raw_row_json->>'班长', '')),
            employee_group = COALESCE(employee_group, NULLIF(raw_row_json->>'员工组', '')),
            employee_subgroup = COALESCE(employee_subgroup, NULLIF(raw_row_json->>'员工子组', '')),
            sub_label = COALESCE(sub_label, NULLIF(raw_row_json->>'子标签', '')),
            entry_date = COALESCE(entry_date, CASE WHEN NULLIF(raw_row_json->>'入职日期', '') ~ '^\d{4}-\d{2}-\d{2}$' THEN (NULLIF(raw_row_json->>'入职日期', ''))::date WHEN NULLIF(raw_row_json->>'入职日期', '') ~ '^\d{4}/\d{2}/\d{2}$' THEN replace(NULLIF(raw_row_json->>'入职日期', ''), '/', '-')::date ELSE NULL END),
            company_seniority_text = COALESCE(company_seniority_text, NULLIF(raw_row_json->>'司龄', '')),
            gender = COALESCE(gender, NULLIF(raw_row_json->>'性别', '')),
            birth_date = COALESCE(birth_date, CASE WHEN NULLIF(raw_row_json->>'出生日期', '') ~ '^\d{4}-\d{2}-\d{2}$' THEN (NULLIF(raw_row_json->>'出生日期', ''))::date WHEN NULLIF(raw_row_json->>'出生日期', '') ~ '^\d{4}/\d{2}/\d{2}$' THEN replace(NULLIF(raw_row_json->>'出生日期', ''), '/', '-')::date ELSE NULL END),
            birthday_type = COALESCE(birthday_type, NULLIF(raw_row_json->>'生日类型', '')),
            actual_birthday = COALESCE(actual_birthday, NULLIF(raw_row_json->>'实际生日', '')),
            age_text = COALESCE(age_text, NULLIF(raw_row_json->>'年龄', '')),
            household_registration_province = COALESCE(household_registration_province, NULLIF(raw_row_json->>'户口所在省', '')),
            household_registration_city = COALESCE(household_registration_city, NULLIF(raw_row_json->>'户口所在市', '')),
            registered_residence = COALESCE(registered_residence, NULLIF(raw_row_json->>'户籍地', '')),
            social_security_location = COALESCE(social_security_location, NULLIF(raw_row_json->>'参保地', '')),
            marital_status = COALESCE(marital_status, NULLIF(raw_row_json->>'婚姻状况', '')),
            education_level = COALESCE(education_level, NULLIF(raw_row_json->>'学历', '')),
            study_mode = COALESCE(study_mode, NULLIF(raw_row_json->>'学习形式', '')),
            graduation_date = COALESCE(graduation_date, CASE WHEN NULLIF(raw_row_json->>'毕业时间', '') ~ '^\d{4}-\d{2}-\d{2}$' THEN (NULLIF(raw_row_json->>'毕业时间', ''))::date WHEN NULLIF(raw_row_json->>'毕业时间', '') ~ '^\d{4}/\d{2}/\d{2}$' THEN replace(NULLIF(raw_row_json->>'毕业时间', ''), '/', '-')::date ELSE NULL END),
            degree = COALESCE(degree, NULLIF(raw_row_json->>'学位', '')),
            school_name = COALESCE(school_name, NULLIF(raw_row_json->>'学校', '')),
            alternate_school_name = COALESCE(alternate_school_name, NULLIF(raw_row_json->>'其他院校', '')),
            major_name = COALESCE(major_name, NULLIF(raw_row_json->>'院校专业', '')),
            id_number = COALESCE(id_number, NULLIF(raw_row_json->>'证件号码', '')),
            phone_number = COALESCE(phone_number, NULLIF(raw_row_json->>'联系电话', '')),
            vanke_email = COALESCE(vanke_email, NULLIF(raw_row_json->>'万科邮箱', '')),
            onewo_email = COALESCE(onewo_email, NULLIF(raw_row_json->>'万物云邮箱', '')),
            domain_account = COALESCE(domain_account, NULLIF(raw_row_json->>'域账号', '')),
            employment_status = COALESCE(employment_status, NULLIF(raw_row_json->>'雇佣状态', '')),
            department_category = COALESCE(department_category, NULLIF(raw_row_json->>'部门分类', '')),
            department_subcategory = COALESCE(department_subcategory, NULLIF(raw_row_json->>'部门子分类', '')),
            external_roster_flag = COALESCE(external_roster_flag, NULLIF(raw_row_json->>'是否外盘人员', '')),
            contract_type = COALESCE(contract_type, NULLIF(raw_row_json->>'合同类型', '')),
            contract_signing_entity = COALESCE(contract_signing_entity, NULLIF(raw_row_json->>'合同签订主体', '')),
            contract_start_date = COALESCE(contract_start_date, CASE WHEN NULLIF(raw_row_json->>'合同开始日期', '') ~ '^\d{4}-\d{2}-\d{2}$' THEN (NULLIF(raw_row_json->>'合同开始日期', ''))::date WHEN NULLIF(raw_row_json->>'合同开始日期', '') ~ '^\d{4}/\d{2}/\d{2}$' THEN replace(NULLIF(raw_row_json->>'合同开始日期', ''), '/', '-')::date ELSE NULL END),
            contract_end_date = COALESCE(contract_end_date, CASE WHEN NULLIF(raw_row_json->>'合同结束日期', '') ~ '^\d{4}-\d{2}-\d{2}$' THEN (NULLIF(raw_row_json->>'合同结束日期', ''))::date WHEN NULLIF(raw_row_json->>'合同结束日期', '') ~ '^\d{4}/\d{2}/\d{2}$' THEN replace(NULLIF(raw_row_json->>'合同结束日期', ''), '/', '-')::date ELSE NULL END),
            start_work_date = COALESCE(start_work_date, CASE WHEN NULLIF(raw_row_json->>'参加工作时间', '') ~ '^\d{4}-\d{2}-\d{2}$' THEN (NULLIF(raw_row_json->>'参加工作时间', ''))::date WHEN NULLIF(raw_row_json->>'参加工作时间', '') ~ '^\d{4}/\d{2}/\d{2}$' THEN replace(NULLIF(raw_row_json->>'参加工作时间', ''), '/', '-')::date ELSE NULL END),
            service_start_date_at_vanke = COALESCE(service_start_date_at_vanke, CASE WHEN NULLIF(raw_row_json->>'服务万科时间', '') ~ '^\d{4}-\d{2}-\d{2}$' THEN (NULLIF(raw_row_json->>'服务万科时间', ''))::date WHEN NULLIF(raw_row_json->>'服务万科时间', '') ~ '^\d{4}/\d{2}/\d{2}$' THEN replace(NULLIF(raw_row_json->>'服务万科时间', ''), '/', '-')::date ELSE NULL END),
            latest_entry_date_to_vanke = COALESCE(latest_entry_date_to_vanke, CASE WHEN NULLIF(raw_row_json->>'最新入职万科日期', '') ~ '^\d{4}-\d{2}-\d{2}$' THEN (NULLIF(raw_row_json->>'最新入职万科日期', ''))::date WHEN NULLIF(raw_row_json->>'最新入职万科日期', '') ~ '^\d{4}/\d{2}/\d{2}$' THEN replace(NULLIF(raw_row_json->>'最新入职万科日期', ''), '/', '-')::date ELSE NULL END),
            seniority_start_date = COALESCE(seniority_start_date, CASE WHEN NULLIF(raw_row_json->>'司龄起算时间', '') ~ '^\d{4}-\d{2}-\d{2}$' THEN (NULLIF(raw_row_json->>'司龄起算时间', ''))::date WHEN NULLIF(raw_row_json->>'司龄起算时间', '') ~ '^\d{4}/\d{2}/\d{2}$' THEN replace(NULLIF(raw_row_json->>'司龄起算时间', ''), '/', '-')::date ELSE NULL END),
            working_years_text = COALESCE(working_years_text, NULLIF(raw_row_json->>'工龄', '')),
            trainee_type = COALESCE(trainee_type, NULLIF(raw_row_json->>'储备见习类型', '')),
            trainee_start_date = COALESCE(trainee_start_date, CASE WHEN NULLIF(raw_row_json->>'储备见习开始日期', '') ~ '^\d{4}-\d{2}-\d{2}$' THEN (NULLIF(raw_row_json->>'储备见习开始日期', ''))::date WHEN NULLIF(raw_row_json->>'储备见习开始日期', '') ~ '^\d{4}/\d{2}/\d{2}$' THEN replace(NULLIF(raw_row_json->>'储备见习开始日期', ''), '/', '-')::date ELSE NULL END),
            trainee_end_date = COALESCE(trainee_end_date, CASE WHEN NULLIF(raw_row_json->>'储备见习结束日期', '') ~ '^\d{4}-\d{2}-\d{2}$' THEN (NULLIF(raw_row_json->>'储备见习结束日期', ''))::date WHEN NULLIF(raw_row_json->>'储备见习结束日期', '') ~ '^\d{4}/\d{2}/\d{2}$' THEN replace(NULLIF(raw_row_json->>'储备见习结束日期', ''), '/', '-')::date ELSE NULL END),
            trainee_post_name = COALESCE(trainee_post_name, NULLIF(raw_row_json->>'储备岗位名称', '')),
            post_remark_property = COALESCE(post_remark_property, NULLIF(raw_row_json->>'岗位备注（物业）', ''), NULLIF(raw_row_json->>'岗位备注(物业)', '')),
            sequence_attribute = COALESCE(sequence_attribute, NULLIF(raw_row_json->>'序列属性', '')),
            sequence_type = COALESCE(sequence_type, NULLIF(raw_row_json->>'序列类型', '')),
            org_path_id = COALESCE(org_path_id, NULLIF(raw_row_json->>'组织路径ID', '')),
            org_path_name = COALESCE(org_path_name, NULLIF(raw_row_json->>'组织路径名称', '')),
            contract_term = COALESCE(contract_term, NULLIF(raw_row_json->>'合同期限', '')),
            military_service_flag = COALESCE(military_service_flag, NULLIF(raw_row_json->>'是否服过兵役', '')),
            discharge_certificate_no = COALESCE(discharge_certificate_no, NULLIF(raw_row_json->>'退役证编号', '')),
            discharge_certificate_type = COALESCE(discharge_certificate_type, NULLIF(raw_row_json->>'退伍证类型', '')),
            enlistment_date = COALESCE(enlistment_date, CASE WHEN NULLIF(raw_row_json->>'入伍时间', '') ~ '^\d{4}-\d{2}-\d{2}$' THEN (NULLIF(raw_row_json->>'入伍时间', ''))::date WHEN NULLIF(raw_row_json->>'入伍时间', '') ~ '^\d{4}/\d{2}/\d{2}$' THEN replace(NULLIF(raw_row_json->>'入伍时间', ''), '/', '-')::date ELSE NULL END),
            discharge_date = COALESCE(discharge_date, CASE WHEN NULLIF(raw_row_json->>'退役时间', '') ~ '^\d{4}-\d{2}-\d{2}$' THEN (NULLIF(raw_row_json->>'退役时间', ''))::date WHEN NULLIF(raw_row_json->>'退役时间', '') ~ '^\d{4}/\d{2}/\d{2}$' THEN replace(NULLIF(raw_row_json->>'退役时间', ''), '/', '-')::date ELSE NULL END),
            leadership_category = COALESCE(leadership_category, NULLIF(raw_row_json->>'领导力类别', '')),
            id_document_permanent_flag = COALESCE(id_document_permanent_flag, NULLIF(raw_row_json->>'证件是否永久有效', '')),
            id_document_valid_from = COALESCE(id_document_valid_from, CASE WHEN NULLIF(raw_row_json->>'证件有效期起', '') ~ '^\d{4}-\d{2}-\d{2}$' THEN (NULLIF(raw_row_json->>'证件有效期起', ''))::date WHEN NULLIF(raw_row_json->>'证件有效期起', '') ~ '^\d{4}/\d{2}/\d{2}$' THEN replace(NULLIF(raw_row_json->>'证件有效期起', ''), '/', '-')::date ELSE NULL END),
            id_document_valid_to = COALESCE(id_document_valid_to, CASE WHEN NULLIF(raw_row_json->>'证件有效期止', '') ~ '^\d{4}-\d{2}-\d{2}$' THEN (NULLIF(raw_row_json->>'证件有效期止', ''))::date WHEN NULLIF(raw_row_json->>'证件有效期止', '') ~ '^\d{4}/\d{2}/\d{2}$' THEN replace(NULLIF(raw_row_json->>'证件有效期止', ''), '/', '-')::date ELSE NULL END),
            primary_position_flag = COALESCE(primary_position_flag, NULLIF(raw_row_json->>'是否主任职', '')),
            employment_type = COALESCE(employment_type, NULLIF(raw_row_json->>'任职类型', '')),
            ethnicity = COALESCE(ethnicity, NULLIF(raw_row_json->>'民族', '')),
            household_registration_type = COALESCE(household_registration_type, NULLIF(raw_row_json->>'户口性质', '')),
            household_registration_location = COALESCE(household_registration_location, NULLIF(raw_row_json->>'户口所在地', '')),
            birthplace = COALESCE(birthplace, NULLIF(raw_row_json->>'出生地', '')),
            native_place = COALESCE(native_place, NULLIF(raw_row_json->>'籍贯', '')),
            nationality = COALESCE(nationality, NULLIF(raw_row_json->>'国籍', '')),
            birth_country = COALESCE(birth_country, NULLIF(raw_row_json->>'出生国家', '')),
            birthplace_province = COALESCE(birthplace_province, NULLIF(raw_row_json->>'出生地所在省', '')),
            birthplace_city = COALESCE(birthplace_city, NULLIF(raw_row_json->>'出生地所在市', '')),
            campus_recruitment_cohort = COALESCE(campus_recruitment_cohort, NULLIF(raw_row_json->>'校招届别', '')),
            political_status = COALESCE(political_status, NULLIF(raw_row_json->>'政治面貌', '')),
            party_organization_name = COALESCE(party_organization_name, NULLIF(raw_row_json->>'所属党组织全称', '')),
            party_member_status = COALESCE(party_member_status, NULLIF(raw_row_json->>'党员状态', '')),
            extra_columns_json = COALESCE(extra_columns_json, CASE WHEN raw_row_json IS NULL THEN NULL ELSE raw_row_json - ARRAY['序号', '公司', '公司ID', '部门', '部门长文本', '部门ID', '部门所属城市', '人员编号', '姓名', '职位编码', '职位名称', '具体岗位(新)', '是否关键岗位', '岗位族', '职务', '一级职能名称', '二级职能名称', '标准岗位编码', '标准岗位名称', '上级编码', '上级名称', '对接HR工号', '对接HR姓名', '班长', '员工组', '员工子组', '子标签', '入职日期', '司龄', '性别', '出生日期', '生日类型', '实际生日', '年龄', '户口所在省', '户口所在市', '户籍地', '参保地', '婚姻状况', '学历', '学习形式', '毕业时间', '学位', '学校', '其他院校', '院校专业', '证件号码', '联系电话', '万科邮箱', '万物云邮箱', '域账号', '雇佣状态', '部门分类', '部门子分类', '是否外盘人员', '合同类型', '合同签订主体', '合同开始日期', '合同结束日期', '参加工作时间', '服务万科时间', '最新入职万科日期', '司龄起算时间', '工龄', '储备见习类型', '储备见习开始日期', '储备见习结束日期', '储备岗位名称', '岗位备注（物业）', '序列属性', '序列类型', '组织路径ID', '组织路径名称', '合同期限', '是否服过兵役', '退役证编号', '退伍证类型', '入伍时间', '退役时间', '领导力类别', '证件是否永久有效', '证件有效期起', '证件有效期止', '是否主任职', '任职类型', '民族', '户口性质', '户口所在地', '出生地', '籍贯', '国籍', '出生国家', '出生地所在省', '出生地所在市', '校招届别', '政治面貌', '所属党组织全称', '党员状态', '具体岗位（新）', '岗位备注(物业)']::text[] END)
        ;
    END IF;
END $$;

ALTER TABLE "在职花名册表" ALTER COLUMN employee_no TYPE TEXT;
ALTER TABLE "在职花名册表" ALTER COLUMN employee_no SET NOT NULL;
ALTER TABLE "在职花名册表" ALTER COLUMN query_date SET NOT NULL;
ALTER TABLE "在职花名册表" ALTER COLUMN source_file_name SET NOT NULL;
ALTER TABLE "在职花名册表" ALTER COLUMN import_batch_no SET NOT NULL;

ALTER TABLE "在职花名册表" DROP CONSTRAINT IF EXISTS uq_active_roster_query_employee;

DO $$
DECLARE
    pk_name text;
BEGIN
    SELECT conname INTO pk_name
    FROM pg_constraint
    WHERE conrelid = '"在职花名册表"'::regclass
      AND contype = 'p';

    IF pk_name IS NOT NULL AND pk_name <> '在职花名册表_employee_no_pkey' THEN
        EXECUTE format('ALTER TABLE "在职花名册表" DROP CONSTRAINT %I', pk_name);
    END IF;
END $$;

ALTER TABLE "在职花名册表" DROP COLUMN IF EXISTS id;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = '"在职花名册表"'::regclass
          AND contype = 'p'
    ) THEN
        ALTER TABLE "在职花名册表" ADD CONSTRAINT "在职花名册表_employee_no_pkey" PRIMARY KEY (employee_no);
    END IF;
END $$;

ALTER TABLE "在职花名册表" DROP COLUMN IF EXISTS raw_row_json;

CREATE INDEX IF NOT EXISTS idx_active_roster_query_date ON "在职花名册表"(query_date);
CREATE INDEX IF NOT EXISTS idx_active_roster_department_id ON "在职花名册表"(department_id);
CREATE INDEX IF NOT EXISTS idx_active_roster_company_id ON "在职花名册表"(company_id);
CREATE INDEX IF NOT EXISTS idx_active_roster_employment_type ON "在职花名册表"(employment_type);
