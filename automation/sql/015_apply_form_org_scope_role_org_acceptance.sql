-- 方案013：申请表组织范围角色组织展开验收 SQL
-- 使用方式：
-- 1. 先完成 014 表结构迁移
-- 2. 再至少采集并写入 1 张权限申请单据
-- 3. 执行本脚本逐项验收

-- 1. 表结构检查
SELECT
    column_name,
    is_nullable,
    data_type
FROM information_schema.columns
WHERE table_schema = current_schema()
  AND table_name = '申请表组织范围'
ORDER BY ordinal_position;

-- 2. 索引检查
SELECT
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = current_schema()
  AND tablename = '申请表组织范围'
ORDER BY indexname;

-- 3. 关键列存在性检查
SELECT
    COUNT(*) FILTER (WHERE column_name = '角色编码') AS has_role_code,
    COUNT(*) FILTER (WHERE column_name = '角色名称') AS has_role_name,
    COUNT(*) FILTER (WHERE column_name = '组织编码' AND is_nullable = 'YES') AS org_code_nullable
FROM information_schema.columns
WHERE table_schema = current_schema()
  AND table_name = '申请表组织范围';

-- 4. 全表概览
SELECT
    COUNT(*) AS total_rows,
    COUNT(*) FILTER (WHERE "组织编码" IS NULL) AS null_org_rows,
    COUNT(*) FILTER (WHERE "组织编码" IS NOT NULL) AS normal_org_rows,
    COUNT(DISTINCT "单据编号") AS distinct_documents,
    COUNT(DISTINCT "角色编码") AS distinct_role_codes
FROM "申请表组织范围";

-- 5. 非空组织编码重复检查
SELECT
    "单据编号",
    "角色编码",
    "组织编码",
    COUNT(*) AS duplicate_count
FROM "申请表组织范围"
WHERE "组织编码" IS NOT NULL
GROUP BY "单据编号", "角色编码", "组织编码"
HAVING COUNT(*) > 1
ORDER BY duplicate_count DESC, "单据编号", "角色编码", "组织编码";

-- 6. NULL 组织编码重复检查
SELECT
    "单据编号",
    "角色编码",
    COUNT(*) AS duplicate_count
FROM "申请表组织范围"
WHERE "组织编码" IS NULL
GROUP BY "单据编号", "角色编码"
HAVING COUNT(*) > 1
ORDER BY duplicate_count DESC, "单据编号", "角色编码";

-- 7. 与权限列表 skip 规则对照检查
SELECT
    s."单据编号",
    s."角色编码",
    MAX(s."角色名称") AS "角色名称",
    p."不检查组织范围",
    COUNT(*) FILTER (WHERE s."组织编码" IS NULL) AS null_org_rows,
    COUNT(*) FILTER (WHERE s."组织编码" IS NOT NULL) AS normal_org_rows
FROM "申请表组织范围" s
LEFT JOIN "权限列表" p
  ON p."角色编码" = s."角色编码"
GROUP BY s."单据编号", s."角色编码", p."不检查组织范围"
ORDER BY s."单据编号", s."角色编码";

-- 8. 违反 skip 规则的角色
-- 8.1 标记为不检查组织范围，但仍写入非 NULL 组织编码
SELECT
    s."单据编号",
    s."角色编码",
    MAX(s."角色名称") AS "角色名称",
    COUNT(*) AS bad_rows
FROM "申请表组织范围" s
JOIN "权限列表" p
  ON p."角色编码" = s."角色编码"
WHERE p."不检查组织范围" = TRUE
  AND s."组织编码" IS NOT NULL
GROUP BY s."单据编号", s."角色编码"
ORDER BY bad_rows DESC, s."单据编号", s."角色编码";

-- 8.2 未标记为不检查组织范围，但却写入 NULL 组织编码
SELECT
    s."单据编号",
    s."角色编码",
    MAX(s."角色名称") AS "角色名称",
    COUNT(*) AS bad_rows
FROM "申请表组织范围" s
LEFT JOIN "权限列表" p
  ON p."角色编码" = s."角色编码"
WHERE COALESCE(p."不检查组织范围", FALSE) = FALSE
  AND s."组织编码" IS NULL
GROUP BY s."单据编号", s."角色编码"
ORDER BY bad_rows DESC, s."单据编号", s."角色编码";

-- 9. 与申请单权限列表角色对照
SELECT
    d."单据编号",
    d."角色编码",
    MAX(d."角色名称") AS detail_role_name,
    COUNT(*) AS detail_rows,
    COUNT(s.*) AS org_scope_rows
FROM "申请单权限列表" d
LEFT JOIN "申请表组织范围" s
  ON s."单据编号" = d."单据编号"
 AND s."角色编码" = d."角色编码"
GROUP BY d."单据编号", d."角色编码"
ORDER BY d."单据编号", d."角色编码";

-- 10. 抽样查看最新 50 行
SELECT
    "组织范围ID",
    "单据编号",
    "角色编码",
    "角色名称",
    "组织编码",
    "记录创建时间"
FROM "申请表组织范围"
ORDER BY "组织范围ID" DESC
LIMIT 50;

