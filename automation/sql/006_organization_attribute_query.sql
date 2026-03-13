CREATE OR REPLACE FUNCTION fn_map_org_unit_name(p_org_full_name TEXT)
RETURNS TEXT
LANGUAGE plpgsql
IMMUTABLE
STRICT
PARALLEL SAFE
AS $$
DECLARE
    l2 TEXT := NULLIF(split_part(p_org_full_name, '_', 2), '');
    l3 TEXT := NULLIF(split_part(p_org_full_name, '_', 3), '');
    l4 TEXT := NULLIF(split_part(p_org_full_name, '_', 4), '');
BEGIN
    IF p_org_full_name = '万物云' THEN
        RETURN '万物云';
    END IF;
    IF p_org_full_name = '万物云_万物云本部' THEN
        RETURN '万物云本部';
    END IF;
    IF l2 = '集团其他BGBU' THEN
        RETURN '集团其他BGBU';
    END IF;

    IF l2 = '投资与创新发展中心' AND l3 = '万物成长被投企业' AND l4 = '重庆天骄' THEN
        RETURN '被投-重庆天骄';
    END IF;
    IF l2 = '投资与创新发展中心' AND l3 = '万物成长被投企业' AND l4 = '福建伯恩' THEN
        RETURN '被投-福建伯恩';
    END IF;
    IF l2 = '蝶城发展中心' AND (l3 LIKE '万物为家研选家%' OR (l3 = '万物为家' AND l4 = '研选家运营中心')) THEN
        RETURN '为家-研选家';
    END IF;
    IF l2 = '蝶城发展中心' AND (l3 = '万物为家朴邻发展业务部' OR (l3 = '万物为家' AND l4 LIKE '朴邻%')) THEN
        RETURN '为家-朴邻';
    END IF;

    IF l2 IN (
        '管理层', '证券与公司治理部', '人力资源与行政服务中心', '财务与资金管理中心', '知之学社',
        '规划发展中心', '数据与信息技术中心', '投创本部', '投资与创新发展中心', '蝶城发展中心',
        '资产经营中心', '政府与企业客户服务中心', '丹田', '祥盈企服', '福讯信息', '万御安防',
        '万物梁行', '万物云城', '万净环卫', '万科物业', '万睿科技', '安徽战区代表处', '福州战区代表处',
        '厦门战区代表处', '山东战区代表处', '杭州战区代表处', '东北战区代表处', '鄂豫战区代表处',
        '湘赣战区代表处', '南京战区代表处', '西北战区代表处', '深圳战区代表处', '津晋战区代表处',
        '京冀战区代表处', '福建战区代表处', '川云战区代表处', '广州战区代表处', '琼桂战区代表处',
        '佛山战区代表处', '苏州战区代表处', '上海战区代表处', '渝贵战区代表处'
    ) THEN
        RETURN l2;
    END IF;

    IF l3 IN (
        '管理层', '证券与公司治理部', '人力资源与行政服务中心', '财务与资金管理中心', '知之学社',
        '规划发展中心', '数据与信息技术中心', '投创本部', '投资与创新发展中心', '蝶城发展中心',
        '资产经营中心', '政府与企业客户服务中心', '丹田', '祥盈企服', '福讯信息', '万御安防',
        '万物梁行', '万物云城', '万净环卫', '万科物业', '万睿科技', '安徽战区代表处', '福州战区代表处',
        '厦门战区代表处', '山东战区代表处', '杭州战区代表处', '东北战区代表处', '鄂豫战区代表处',
        '湘赣战区代表处', '南京战区代表处', '西北战区代表处', '深圳战区代表处', '津晋战区代表处',
        '京冀战区代表处', '福建战区代表处', '川云战区代表处', '广州战区代表处', '琼桂战区代表处',
        '佛山战区代表处', '苏州战区代表处', '上海战区代表处', '渝贵战区代表处'
    ) THEN
        RETURN l3;
    END IF;

    RETURN NULL;
END;
$$;


CREATE OR REPLACE FUNCTION fn_map_org_unit_rule(p_org_full_name TEXT)
RETURNS TEXT
LANGUAGE plpgsql
IMMUTABLE
STRICT
PARALLEL SAFE
AS $$
DECLARE
    l2 TEXT := NULLIF(split_part(p_org_full_name, '_', 2), '');
    l3 TEXT := NULLIF(split_part(p_org_full_name, '_', 3), '');
    l4 TEXT := NULLIF(split_part(p_org_full_name, '_', 4), '');
BEGIN
    IF p_org_full_name = '万物云' THEN
        RETURN '顶层同名';
    END IF;
    IF p_org_full_name = '万物云_万物云本部' THEN
        RETURN '顶层同名';
    END IF;
    IF l2 = '集团其他BGBU' THEN
        RETURN '顶层同名';
    END IF;

    IF l2 = '投资与创新发展中心' AND l3 = '万物成长被投企业' AND l4 = '重庆天骄' THEN
        RETURN '细粒度-重庆天骄';
    END IF;
    IF l2 = '投资与创新发展中心' AND l3 = '万物成长被投企业' AND l4 = '福建伯恩' THEN
        RETURN '细粒度-福建伯恩';
    END IF;
    IF l2 = '蝶城发展中心' AND (l3 LIKE '万物为家研选家%' OR (l3 = '万物为家' AND l4 = '研选家运营中心')) THEN
        RETURN '细粒度-研选家';
    END IF;
    IF l2 = '蝶城发展中心' AND (l3 = '万物为家朴邻发展业务部' OR (l3 = '万物为家' AND l4 LIKE '朴邻%')) THEN
        RETURN '细粒度-朴邻';
    END IF;

    IF l2 IN (
        '管理层', '证券与公司治理部', '人力资源与行政服务中心', '财务与资金管理中心', '知之学社',
        '规划发展中心', '数据与信息技术中心', '投创本部', '投资与创新发展中心', '蝶城发展中心',
        '资产经营中心', '政府与企业客户服务中心', '丹田', '祥盈企服', '福讯信息', '万御安防',
        '万物梁行', '万物云城', '万净环卫', '万科物业', '万睿科技', '安徽战区代表处', '福州战区代表处',
        '厦门战区代表处', '山东战区代表处', '杭州战区代表处', '东北战区代表处', '鄂豫战区代表处',
        '湘赣战区代表处', '南京战区代表处', '西北战区代表处', '深圳战区代表处', '津晋战区代表处',
        '京冀战区代表处', '福建战区代表处', '川云战区代表处', '广州战区代表处', '琼桂战区代表处',
        '佛山战区代表处', '苏州战区代表处', '上海战区代表处', '渝贵战区代表处'
    ) THEN
        RETURN 'L2直接命中';
    END IF;

    IF l3 IN (
        '管理层', '证券与公司治理部', '人力资源与行政服务中心', '财务与资金管理中心', '知之学社',
        '规划发展中心', '数据与信息技术中心', '投创本部', '投资与创新发展中心', '蝶城发展中心',
        '资产经营中心', '政府与企业客户服务中心', '丹田', '祥盈企服', '福讯信息', '万御安防',
        '万物梁行', '万物云城', '万净环卫', '万科物业', '万睿科技', '安徽战区代表处', '福州战区代表处',
        '厦门战区代表处', '山东战区代表处', '杭州战区代表处', '东北战区代表处', '鄂豫战区代表处',
        '湘赣战区代表处', '南京战区代表处', '西北战区代表处', '深圳战区代表处', '津晋战区代表处',
        '京冀战区代表处', '福建战区代表处', '川云战区代表处', '广州战区代表处', '琼桂战区代表处',
        '佛山战区代表处', '苏州战区代表处', '上海战区代表处', '渝贵战区代表处'
    ) THEN
        RETURN 'L3直接命中';
    END IF;

    RETURN '未匹配';
END;
$$;


CREATE OR REPLACE FUNCTION fn_map_process_level_name_override(p_org_full_name TEXT)
RETURNS TEXT
LANGUAGE sql
IMMUTABLE
STRICT
PARALLEL SAFE
AS $$
    SELECT CASE
        WHEN NULLIF(split_part(p_org_full_name, '_', 2), '') = '蝶城发展中心'
         AND NULLIF(split_part(p_org_full_name, '_', 3), '') = '人力资源与行政服务部'
         AND COALESCE(NULLIF(split_part(p_org_full_name, '_', 4), ''), '__EMPTY__') <> '研选家人力资源组'
        THEN '蝶发人行部'
        WHEN NULLIF(split_part(p_org_full_name, '_', 3), '') = '人力资源与行政服务中心'
         AND NULLIF(split_part(p_org_full_name, '_', 4), '') IS NOT NULL
        THEN NULLIF(split_part(p_org_full_name, '_', 4), '')
        ELSE NULL
    END
$$;


CREATE OR REPLACE FUNCTION fn_map_wanyu_city_sales_department(p_org_full_name TEXT)
RETURNS TEXT
LANGUAGE sql
IMMUTABLE
STRICT
PARALLEL SAFE
AS $$
    SELECT CASE
        WHEN RIGHT(NULLIF(split_part(p_org_full_name, '_', 4), ''), 5) = '城市营业部'
        THEN NULLIF(split_part(p_org_full_name, '_', 4), '')
        ELSE NULL
    END
$$;


CREATE OR REPLACE FUNCTION fn_map_process_level_category(
    p_process_level_name_resolved TEXT,
    p_company_name TEXT,
    p_org_full_name TEXT
)
RETURNS TEXT
LANGUAGE sql
IMMUTABLE
PARALLEL SAFE
AS $$
    SELECT CASE
        WHEN NULLIF(BTRIM(p_company_name), '') = '人事远程交付中心' THEN '人事远程交付中心'
        WHEN NULLIF(split_part(p_org_full_name, '_', 3), '') = '人力资源与行政服务中心'
         AND NULLIF(split_part(p_org_full_name, '_', 4), '') IS NOT NULL
         AND NULLIF(split_part(p_org_full_name, '_', 4), '') <> 'BG人力资源行政服务中心'
         AND RIGHT(NULLIF(BTRIM(p_org_full_name), ''), 7) = '人事交付服务组'
        THEN '属地服务站'
        WHEN NULLIF(split_part(p_org_full_name, '_', 3), '') = '人力资源与行政服务中心'
         AND NULLIF(split_part(p_org_full_name, '_', 4), '') IS NOT NULL
         AND NULLIF(split_part(p_org_full_name, '_', 4), '') <> 'BG人力资源行政服务中心'
        THEN '战区人行部门'
        WHEN NULLIF(BTRIM(p_process_level_name_resolved), '') IS NULL THEN NULL
        WHEN NULLIF(BTRIM(p_process_level_name_resolved), '') IN (
            '万物云本部',
            '本部部门',
            '本部二级部门',
            '本部三级部门',
            '万科物业'
        ) THEN '万物云本部'
        WHEN NULLIF(BTRIM(p_process_level_name_resolved), '') IN (
            '本部',
            '修缮业务本部',
            '朴邻本部',
            '万御电梯本部',
            '福讯信息'
        ) THEN '业务单元本部'
        ELSE '属地组织'
    END
$$;


CREATE OR REPLACE FUNCTION fn_map_org_auth_level(
    p_org_code TEXT,
    p_org_level TEXT,
    p_physical_level TEXT,
    p_org_full_name TEXT
)
RETURNS TEXT
LANGUAGE plpgsql
IMMUTABLE
PARALLEL SAFE
AS $$
DECLARE
    normalized_org_code TEXT := NULLIF(BTRIM(p_org_code), '');
    normalized_org_full_name TEXT := NULLIF(BTRIM(p_org_full_name), '');
    physical_level_num NUMERIC := CASE
        WHEN NULLIF(BTRIM(p_physical_level), '') ~ '^[0-9]+([.][0-9]+)?$' THEN NULLIF(BTRIM(p_physical_level), '')::NUMERIC
        ELSE NULL
    END;
BEGIN
    IF normalized_org_code IN (
        '50907939',
        '50802218',
        '50802206',
        '50915927',
        '50802202',
        '55002557',
        '50802204',
        '50907940',
        '50916400',
        '99999998'
    ) THEN
        RETURN '一级授权';
    END IF;

    IF COALESCE(normalized_org_full_name, '') LIKE '%BG人力资源行政服务中心%' THEN
        RETURN '一级授权';
    END IF;

    IF physical_level_num = 2 THEN
        RETURN '二级授权';
    END IF;

    RETURN NULL;
END;
$$;


CREATE OR REPLACE FUNCTION fn_map_org_auth_level_rule(
    p_org_code TEXT,
    p_org_level TEXT,
    p_physical_level TEXT,
    p_org_full_name TEXT
)
RETURNS TEXT
LANGUAGE plpgsql
IMMUTABLE
PARALLEL SAFE
AS $$
DECLARE
    normalized_org_code TEXT := NULLIF(BTRIM(p_org_code), '');
    normalized_org_full_name TEXT := NULLIF(BTRIM(p_org_full_name), '');
    physical_level_num NUMERIC := CASE
        WHEN NULLIF(BTRIM(p_physical_level), '') ~ '^[0-9]+([.][0-9]+)?$' THEN NULLIF(BTRIM(p_physical_level), '')::NUMERIC
        ELSE NULL
    END;
BEGIN
    IF normalized_org_code IN (
        '50907939',
        '50802218',
        '50802206',
        '50915927',
        '50802202',
        '55002557',
        '50802204',
        '50907940',
        '50916400',
        '99999998'
    ) THEN
        RETURN 'org_code:l1_specified';
    END IF;

    IF COALESCE(normalized_org_full_name, '') LIKE '%BG人力资源行政服务中心%' THEN
        RETURN 'org_full_name:contains_BG人力资源行政服务中心';
    END IF;

    IF physical_level_num = 2 THEN
        RETURN 'physical_level:eq_2';
    END IF;

    RETURN 'unresolved';
END;
$$;


CREATE TABLE IF NOT EXISTS "组织属性查询" (
    org_code TEXT PRIMARY KEY,
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
);

ALTER TABLE "组织属性查询"
    ADD COLUMN IF NOT EXISTS wanyu_city_sales_department TEXT;

ALTER TABLE "组织属性查询"
    ADD COLUMN IF NOT EXISTS process_level_category TEXT;

ALTER TABLE "组织属性查询"
    ADD COLUMN IF NOT EXISTS org_auth_level TEXT;

ALTER TABLE "组织属性查询"
    ADD COLUMN IF NOT EXISTS org_auth_level_rule TEXT;

ALTER TABLE "组织属性查询"
    DROP COLUMN IF EXISTS hr_admin_center_name;

CREATE INDEX IF NOT EXISTS idx_组织属性查询_org_name ON "组织属性查询" (org_name);
CREATE INDEX IF NOT EXISTS idx_组织属性查询_parent_org_code ON "组织属性查询" (parent_org_code);
CREATE INDEX IF NOT EXISTS idx_组织属性查询_company_name ON "组织属性查询" (company_name);
CREATE INDEX IF NOT EXISTS idx_组织属性查询_org_level ON "组织属性查询" (org_level);
CREATE INDEX IF NOT EXISTS idx_组织属性查询_city_name ON "组织属性查询" (city_name);
CREATE INDEX IF NOT EXISTS idx_组织属性查询_process_level_category ON "组织属性查询" (process_level_category);
CREATE INDEX IF NOT EXISTS idx_组织属性查询_dept_category_code ON "组织属性查询" (dept_category_code);
CREATE INDEX IF NOT EXISTS idx_组织属性查询_dept_subcategory_code ON "组织属性查询" (dept_subcategory_code);
CREATE INDEX IF NOT EXISTS idx_组织属性查询_org_unit_name ON "组织属性查询" (org_unit_name);
CREATE INDEX IF NOT EXISTS idx_组织属性查询_org_auth_level ON "组织属性查询" (org_auth_level);
CREATE INDEX IF NOT EXISTS idx_组织属性查询_wanyu_city_sales_department ON "组织属性查询" (wanyu_city_sales_department);
CREATE INDEX IF NOT EXISTS idx_组织属性查询_war_zone ON "组织属性查询" (war_zone);
CREATE INDEX IF NOT EXISTS idx_组织属性查询_war_zone_city_name ON "组织属性查询" (war_zone, city_name);
CREATE INDEX IF NOT EXISTS idx_组织属性查询_org_unit_name_company_name ON "组织属性查询" (org_unit_name, company_name);


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
            COALESCE(fn_map_process_level_name_override(o.org_full_name), rpl.process_level_name_resolved) AS process_level_name_resolved,
            fn_map_process_level_category(
                COALESCE(fn_map_process_level_name_override(o.org_full_name), rpl.process_level_name_resolved),
                o.company_name,
                o.org_full_name
            ) AS process_level_category,
            o.dept_subcategory_code,
            o.dept_subcategory_name,
            o.dept_category_code,
            o.dept_category_name,
            o.org_created_time,
            o.org_full_name,
            fn_map_org_unit_name(o.org_full_name) AS org_unit_name,
            fn_map_org_unit_rule(o.org_full_name) AS org_unit_rule,
            fn_map_org_auth_level(o.org_code, o.org_level, o.physical_level, o.org_full_name) AS org_auth_level,
            fn_map_org_auth_level_rule(o.org_code, o.org_level, o.physical_level, o.org_full_name) AS org_auth_level_rule,
            fn_map_wanyu_city_sales_department(o.org_full_name) AS wanyu_city_sales_department,
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
