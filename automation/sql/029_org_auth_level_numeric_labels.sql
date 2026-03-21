-- 组织授权级别标签改造：
-- 一级/二级/三级/四级授权 -> 1级/2级/3级/4级授权
-- 未命中规则的空值统一改为“未分类”

BEGIN;

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

COMMIT;
