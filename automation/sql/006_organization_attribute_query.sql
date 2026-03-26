CREATE OR REPLACE FUNCTION fn_is_retired_org_unit_l2(p_l2 TEXT)
RETURNS BOOLEAN
LANGUAGE sql
IMMUTABLE
STRICT
PARALLEL SAFE
AS $$
    SELECT p_l2 IN (
        '福建伯恩物业集团有限公司', '杭州物业（中心城市）', '政企空间服务事业部', '业财法人组织', '公司服务中心',
        '住宅项目运营中心', '物业发展', '北京战区', '广州物业（中心城市）', '东莞物业（中心城市）',
        '誉鹰物业', '万物仓', '成都战区', '合肥城市代表处', '北京商企公司', '浙江耀江物业',
        '设施管理运营中心', '幸福社区发展中心50901406', '北京物业', '昆明物业', '华东区域', '华北区域',
        '华南区域', '中西区域', '吉黑战区代表处', 'F02广州中南', '万物社区业务部',
        '资产经营中心50974450', 'F01广州西北', 'F03广州东清管理中心', '海南物业', '物业事业本部',
        '珠海万物云', '惠州物业', 'F广州大区', '南京战区', '万物成长咨询服务公司', '上海战区', '佛山战区',
        '厦门战区', '广州万盈物业50927570', '广州万盈物业50927609', '广州战区', '房产经纪运营管理中心',
        '杭州战区', '武汉战区', '沈阳战区', '深圳战区', '福建伯恩物业集团有限公司50932028',
        '福建伯恩物业集团有限公司50932030', '自营装修发展中心-作废', '苏州战区', '长春战区', '青岛战区'
    )
$$;


CREATE OR REPLACE FUNCTION fn_map_retired_org_unit_l3(p_l2 TEXT, p_l3 TEXT)
RETURNS TEXT
LANGUAGE sql
IMMUTABLE
PARALLEL SAFE
AS $$
    SELECT CASE
        WHEN p_l2 = '万物云本部'
         AND p_l3 IN (
            '人力资源部B',
            '住这儿商业化工作室A',
            '规划发展部B',
            '证券与公司治理部50974733',
            '财务及运营管理部B',
            '测试'
         )
        THEN '（作废）' || p_l3
        ELSE NULL
    END
$$;


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

    IF fn_map_retired_org_unit_l3(l2, l3) IS NOT NULL THEN
        RETURN fn_map_retired_org_unit_l3(l2, l3);
    END IF;

    IF fn_is_retired_org_unit_l2(l2) THEN
        RETURN '（作废）' || l2;
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

    IF fn_map_retired_org_unit_l3(l2, l3) IS NOT NULL THEN
        RETURN 'L3作废映射';
    END IF;

    IF fn_is_retired_org_unit_l2(l2) THEN
        RETURN 'L2作废映射';
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
        WHEN COALESCE(NULLIF(BTRIM(p_org_full_name), ''), '') LIKE '%BG人力资源行政服务中心%'
          OR COALESCE(NULLIF(BTRIM(p_org_full_name), ''), '') LIKE '%知之学社%'
        THEN 'BG人行中心与学社'
        WHEN NULLIF(split_part(p_org_full_name, '_', 2), '') = '蝶城发展中心'
         AND NULLIF(split_part(p_org_full_name, '_', 3), '') = '人力资源与行政服务部'
         AND COALESCE(NULLIF(split_part(p_org_full_name, '_', 4), ''), '__EMPTY__') <> '研选家人力资源组'
        THEN '蝶发人行部'
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
    p_org_full_name TEXT,
    p_org_unit_name TEXT,
    p_process_level_category TEXT
)
RETURNS TEXT
LANGUAGE plpgsql
IMMUTABLE
PARALLEL SAFE
AS $$
DECLARE
    normalized_org_code TEXT := NULLIF(BTRIM(p_org_code), '');
    normalized_org_full_name TEXT := NULLIF(BTRIM(p_org_full_name), '');
    normalized_org_unit_name TEXT := NULLIF(BTRIM(p_org_unit_name), '');
    normalized_process_level_category TEXT := NULLIF(BTRIM(p_process_level_category), '');
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
        '99999998',
        '50907621',
        '50916021'
    ) THEN
        RETURN '1级授权';
    END IF;

    IF COALESCE(normalized_org_full_name, '') LIKE '%BG人力资源行政服务中心%' THEN
        RETURN '1级授权';
    END IF;

    IF normalized_org_code IN (
        '50939479',
        '50921744'
    ) THEN
        RETURN '2级授权';
    END IF;

    IF COALESCE(normalized_org_unit_name, '') LIKE '（作废）%'
       AND physical_level_num = 2 THEN
        RETURN '2级授权';
    END IF;

    IF normalized_process_level_category = '业务单元本部'
       AND normalized_org_unit_name = '万睿科技'
       AND physical_level_num <= 4 THEN
        RETURN '3级授权';
    END IF;

    IF normalized_process_level_category = '业务单元本部'
       AND physical_level_num <= 3 THEN
        RETURN '2级授权';
    END IF;

    IF normalized_process_level_category = '蝶发人行部' THEN
        RETURN '2级授权';
    END IF;

    IF normalized_process_level_category = '业务单元本部'
       AND physical_level_num >= 4 THEN
        RETURN '3级授权';
    END IF;

    IF physical_level_num = 2 THEN
        RETURN '2级授权';
    END IF;

    IF physical_level_num = 3 THEN
        RETURN '3级授权';
    END IF;

    IF normalized_process_level_category = '属地组织'
       AND physical_level_num >= 4 THEN
        RETURN '4级授权';
    END IF;

    IF normalized_process_level_category IS NULL
       AND physical_level_num >= 6 THEN
        RETURN '4级授权';
    END IF;

    RETURN '未分类';
END;
$$;


CREATE OR REPLACE FUNCTION fn_map_org_auth_level_rule(
    p_org_code TEXT,
    p_org_level TEXT,
    p_physical_level TEXT,
    p_org_full_name TEXT,
    p_org_unit_name TEXT,
    p_process_level_category TEXT
)
RETURNS TEXT
LANGUAGE plpgsql
IMMUTABLE
PARALLEL SAFE
AS $$
DECLARE
    normalized_org_code TEXT := NULLIF(BTRIM(p_org_code), '');
    normalized_org_full_name TEXT := NULLIF(BTRIM(p_org_full_name), '');
    normalized_org_unit_name TEXT := NULLIF(BTRIM(p_org_unit_name), '');
    normalized_process_level_category TEXT := NULLIF(BTRIM(p_process_level_category), '');
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
        '99999998',
        '50907621',
        '50916021'
    ) THEN
        RETURN 'org_code:l1_specified';
    END IF;

    IF COALESCE(normalized_org_full_name, '') LIKE '%BG人力资源行政服务中心%' THEN
        RETURN 'org_full_name:contains_BG人力资源行政服务中心';
    END IF;

    IF normalized_org_code IN (
        '50939479',
        '50921744'
    ) THEN
        RETURN 'org_code:l2_specified';
    END IF;

    IF COALESCE(normalized_org_unit_name, '') LIKE '（作废）%'
       AND physical_level_num = 2 THEN
        RETURN 'org_unit_name:startswith_（作废）_and_physical_level:eq_2';
    END IF;

    IF normalized_process_level_category = '业务单元本部'
       AND normalized_org_unit_name = '万睿科技'
       AND physical_level_num <= 4 THEN
        RETURN 'process_level_category:业务单元本部_and_org_unit_name:万睿科技_and_physical_level:lte_4';
    END IF;

    IF normalized_process_level_category = '业务单元本部'
       AND physical_level_num <= 3 THEN
        RETURN 'process_level_category:业务单元本部_and_physical_level:lte_3';
    END IF;

    IF normalized_process_level_category = '蝶发人行部' THEN
        RETURN 'process_level_category:蝶发人行部';
    END IF;

    IF normalized_process_level_category = '业务单元本部'
       AND physical_level_num >= 4 THEN
        RETURN 'process_level_category:业务单元本部_and_physical_level:gte_4';
    END IF;

    IF physical_level_num = 2 THEN
        RETURN 'physical_level:eq_2';
    END IF;

    IF physical_level_num = 3 THEN
        RETURN 'physical_level:eq_3';
    END IF;

    IF normalized_process_level_category = '属地组织'
       AND physical_level_num >= 4 THEN
        RETURN 'process_level_category:属地组织_and_physical_level:gte_4';
    END IF;

    IF normalized_process_level_category IS NULL
       AND physical_level_num >= 6 THEN
        RETURN 'process_level_category:<NULL>_and_physical_level:gte_6';
    END IF;

    RETURN 'unresolved';
END;
$$;


CREATE TABLE IF NOT EXISTS "组织属性查询" (
    "行政组织编码" TEXT PRIMARY KEY,
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
);

CREATE INDEX IF NOT EXISTS idx_组织属性查询_org_name ON "组织属性查询" ("行政组织名称");
CREATE INDEX IF NOT EXISTS idx_组织属性查询_parent_org_code ON "组织属性查询" ("上级行政组织编码");
CREATE INDEX IF NOT EXISTS idx_组织属性查询_company_name ON "组织属性查询" ("所属公司");
CREATE INDEX IF NOT EXISTS idx_组织属性查询_org_level ON "组织属性查询" ("行政组织层级");
CREATE INDEX IF NOT EXISTS idx_组织属性查询_city_name ON "组织属性查询" ("所在城市");
CREATE INDEX IF NOT EXISTS idx_组织属性查询_process_level_category ON "组织属性查询" ("组织流程层级分类");
CREATE INDEX IF NOT EXISTS idx_组织属性查询_dept_category_code ON "组织属性查询" ("部门分类_编码");
CREATE INDEX IF NOT EXISTS idx_组织属性查询_dept_subcategory_code ON "组织属性查询" ("部门子分类_编码");
CREATE INDEX IF NOT EXISTS idx_组织属性查询_org_unit_name ON "组织属性查询" ("组织单位");
CREATE INDEX IF NOT EXISTS idx_组织属性查询_org_auth_level ON "组织属性查询" ("组织授权级别");
CREATE INDEX IF NOT EXISTS idx_组织属性查询_wanyu_city_sales_department ON "组织属性查询" ("万御城市营业部");
CREATE INDEX IF NOT EXISTS idx_组织属性查询_war_zone ON "组织属性查询" ("所属战区");
CREATE INDEX IF NOT EXISTS idx_组织属性查询_war_zone_city_name ON "组织属性查询" ("所属战区", "所在城市");
CREATE INDEX IF NOT EXISTS idx_组织属性查询_org_unit_name_company_name ON "组织属性查询" ("组织单位", "所属公司");


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
    EXECUTE 'TRUNCATE TABLE "组织属性查询"';
    EXECUTE '
        INSERT INTO "组织属性查询" (
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
        SELECT
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
        FROM "组织属性查询__staging"
    ';
    EXECUTE 'DROP TABLE "组织属性查询__staging"';
    EXECUTE 'ANALYZE "组织属性查询"';
END;
$$;

