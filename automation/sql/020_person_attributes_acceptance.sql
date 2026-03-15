-- 方案010：人员属性查询验收 SQL
-- 使用方式：
-- 1. 先完成 019_person_attributes.sql 建表
-- 2. 再发布新代码
-- 3. 至少执行 1 次在职花名册全量导入，触发刷新 人员属性查询
-- 4. 执行本脚本逐项验收

-- 1. 申请单基本信息表结构检查
-- 目标：确认主表不再承载 HR 判定字段
SELECT
    column_name,
    is_nullable,
    data_type
FROM information_schema.columns
WHERE table_schema = current_schema()
  AND table_name = '申请单基本信息'
ORDER BY ordinal_position;

-- 2. 申请单基本信息中旧 HR 列盘点
-- 目标：执行 021 收口迁移后，此处应全部返回 0
SELECT
    COUNT(*) FILTER (WHERE column_name = '花名册匹配状态') AS has_roster_match_status,
    COUNT(*) FILTER (WHERE column_name = '申请人HR类型') AS has_hr_type,
    COUNT(*) FILTER (WHERE column_name = '是否责任HR') AS has_is_responsible_hr,
    COUNT(*) FILTER (WHERE column_name = '是否HR人员') AS has_is_hr_staff,
    COUNT(*) FILTER (WHERE column_name = '是否疑似HR人员') AS has_is_suspected_hr_staff,
    COUNT(*) FILTER (WHERE column_name = 'HR主判定依据') AS has_hr_primary_evidence,
    COUNT(*) FILTER (WHERE column_name = 'HR主判定值') AS has_hr_primary_value,
    COUNT(*) FILTER (WHERE column_name = 'HR子域') AS has_hr_subdomain,
    COUNT(*) FILTER (WHERE column_name = 'HR判定原因') AS has_hr_judgement_reason
FROM information_schema.columns
WHERE table_schema = current_schema()
  AND table_name = '申请单基本信息';

-- 3. 人员属性查询表结构检查
SELECT
    column_name,
    is_nullable,
    data_type
FROM information_schema.columns
WHERE table_schema = current_schema()
  AND table_name = '人员属性查询'
ORDER BY ordinal_position;

-- 4. 人员属性查询索引与主键检查
SELECT
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = current_schema()
  AND tablename = '人员属性查询'
ORDER BY indexname;

-- 5. 花名册与人员属性查询行数对比
-- 目标：两边按工号去重后的行数应一致
WITH roster AS (
    SELECT COUNT(DISTINCT BTRIM("人员编号")) AS roster_employee_count
    FROM "在职花名册表"
    WHERE NULLIF(BTRIM("人员编号"), '') IS NOT NULL
),
person_attr AS (
    SELECT COUNT(*) AS person_attribute_count
    FROM "人员属性查询"
)
SELECT
    roster.roster_employee_count,
    person_attr.person_attribute_count,
    person_attr.person_attribute_count - roster.roster_employee_count AS diff_count
FROM roster, person_attr;

-- 6. 工号差集检查
-- 6.1 花名册中存在，但人员属性查询中缺失
SELECT
    BTRIM(r."人员编号") AS "工号"
FROM "在职花名册表" r
LEFT JOIN "人员属性查询" p
  ON p."工号" = BTRIM(r."人员编号")
WHERE NULLIF(BTRIM(r."人员编号"), '') IS NOT NULL
  AND p."工号" IS NULL
ORDER BY BTRIM(r."人员编号")
LIMIT 100;

-- 6.2 人员属性查询中存在，但花名册中缺失
SELECT
    p."工号"
FROM "人员属性查询" p
LEFT JOIN "在职花名册表" r
  ON BTRIM(r."人员编号") = p."工号"
WHERE r."人员编号" IS NULL
ORDER BY p."工号"
LIMIT 100;

-- 7. 人员属性查询全表概览
SELECT
    COUNT(*) AS total_rows,
    COUNT(*) FILTER (WHERE "申请人HR类型" = 'H1') AS h1_rows,
    COUNT(*) FILTER (WHERE "申请人HR类型" = 'H2') AS h2_rows,
    COUNT(*) FILTER (WHERE "申请人HR类型" = 'H3') AS h3_rows,
    COUNT(*) FILTER (WHERE "申请人HR类型" = 'HY') AS hy_rows,
    COUNT(*) FILTER (WHERE "申请人HR类型" = 'HX') AS hx_rows,
    COUNT(*) FILTER (WHERE "是否责任HR" = TRUE) AS responsible_hr_rows,
    COUNT(*) FILTER (WHERE "花名册匹配状态" = 'UNMATCHED') AS unmatched_rows
FROM "人员属性查询";

-- 8. 关键来源字段空值盘点
SELECT
    COUNT(*) FILTER (WHERE NULLIF(BTRIM("姓名"), '') IS NULL) AS empty_employee_name_rows,
    COUNT(*) FILTER (WHERE NULLIF(BTRIM("部门ID"), '') IS NULL) AS empty_department_id_rows,
    COUNT(*) FILTER (WHERE NULLIF(BTRIM("职位名称"), '') IS NULL) AS empty_position_name_rows,
    COUNT(*) FILTER (WHERE NULLIF(BTRIM("组织路径名称"), '') IS NULL) AS empty_org_path_rows,
    COUNT(*) FILTER (WHERE NULLIF(BTRIM("花名册导入批次号"), '') IS NULL) AS empty_roster_batch_rows
FROM "人员属性查询";

-- 9. HR 结果与布尔派生一致性检查
-- 9.1 H1/H2/H3 但 是否HR人员 = FALSE
SELECT
    "工号",
    "姓名",
    "申请人HR类型",
    "是否HR人员"
FROM "人员属性查询"
WHERE "申请人HR类型" IN ('H1', 'H2', 'H3')
  AND COALESCE("是否HR人员", FALSE) = FALSE
ORDER BY "工号"
LIMIT 100;

-- 9.2 HY 但 是否疑似HR人员 = FALSE
SELECT
    "工号",
    "姓名",
    "申请人HR类型",
    "是否疑似HR人员"
FROM "人员属性查询"
WHERE "申请人HR类型" = 'HY'
  AND COALESCE("是否疑似HR人员", FALSE) = FALSE
ORDER BY "工号"
LIMIT 100;

-- 9.3 HX/HY 却标记为 是否HR人员 = TRUE
SELECT
    "工号",
    "姓名",
    "申请人HR类型",
    "是否HR人员"
FROM "人员属性查询"
WHERE "申请人HR类型" IN ('HX', 'HY')
  AND COALESCE("是否HR人员", FALSE) = TRUE
ORDER BY "工号"
LIMIT 100;

-- 10. 申请单与人员属性查询关联命中率
WITH apply_employees AS (
    SELECT DISTINCT BTRIM("工号") AS employee_no
    FROM "申请单基本信息"
    WHERE NULLIF(BTRIM("工号"), '') IS NOT NULL
)
SELECT
    COUNT(*) AS apply_employee_count,
    COUNT(*) FILTER (WHERE p."工号" IS NOT NULL) AS matched_person_attribute_count,
    COUNT(*) FILTER (WHERE p."工号" IS NULL) AS unmatched_person_attribute_count
FROM apply_employees a
LEFT JOIN "人员属性查询" p
  ON p."工号" = a.employee_no;

-- 11. 最近申请单关联抽样
SELECT
    b."单据编号",
    b."工号",
    p."姓名",
    p."一级职能名称",
    p."二级职能名称",
    p."职位名称",
    p."组织路径名称",
    p."万御城市营业部",
    p."申请人HR类型",
    p."HR主判定依据",
    p."HR主判定值",
    p."HR判定原因",
    p."花名册导入批次号",
    p."责任HR导入批次号"
FROM "申请单基本信息" b
LEFT JOIN "人员属性查询" p
  ON p."工号" = BTRIM(b."工号")
ORDER BY b."记录更新时间" DESC, b."单据编号" DESC
LIMIT 50;

-- 12. 人员属性查询最新抽样
SELECT
    "工号",
    "姓名",
    "部门ID",
    "一级职能名称",
    "二级职能名称",
    "职位名称",
    "标准岗位名称",
    "组织路径名称",
    "万御城市营业部",
    "申请人HR类型",
    "HR主判定依据",
    "HR主判定值",
    "HR子域",
    "HR判定原因",
    "花名册导入批次号",
    "责任HR导入批次号",
    "记录更新时间"
FROM "人员属性查询"
ORDER BY "记录更新时间" DESC, "工号"
LIMIT 50;
