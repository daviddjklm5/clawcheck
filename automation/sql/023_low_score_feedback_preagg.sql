DROP VIEW IF EXISTS "申请单低分反馈预聚合视图";
DROP VIEW IF EXISTS "申请单低分明细富化视图";

CREATE OR REPLACE VIEW "申请单低分明细富化视图" AS
WITH "申请角色首行" AS (
    SELECT
        BTRIM("单据编号") AS "单据编号",
        BTRIM("角色编码") AS "角色编码",
        MIN(NULLIF(BTRIM("明细行号"), '')) AS "明细行号",
        MAX(NULLIF(BTRIM("角色名称"), '')) AS "角色名称"
    FROM "申请单权限列表"
    GROUP BY BTRIM("单据编号"), BTRIM("角色编码")
)
SELECT
    detail."评估明细ID",
    BTRIM(detail."单据编号") AS "单据编号",
    BTRIM(detail."评估批次号") AS "评估批次号",
    BTRIM(detail."评估版本") AS "评估版本",
    detail."维度名称",
    BTRIM(detail."命中规则编码") AS "命中规则编码",
    detail."命中规则说明",
    detail."维度得分",
    detail."明细结论",
    detail."建议干预动作",
    detail."证据摘要",
    BTRIM(detail."角色编码") AS "角色编码",
    COALESCE(
        NULLIF(BTRIM(detail."角色名称"), ''),
        "申请角色首行"."角色名称",
        NULLIF(BTRIM(catalog."角色名称"), '')
    ) AS "角色名称",
    "申请角色首行"."明细行号" AS "明细行号",
    catalog."权限级别",
    catalog."不检查组织范围",
    BTRIM(detail."组织编码") AS "组织编码",
    org."行政组织名称",
    org."物理层级",
    org."组织单位" AS "目标组织单位",
    org."组织授权级别",
    BTRIM(basic."工号") AS "工号",
    person."申请人HR类型",
    person."职位名称" AS "申请人职位名称",
    person."一级职能名称",
    applicant_org."组织流程层级分类" AS "申请人组织流程层级分类",
    applicant_org."组织单位" AS "申请人组织单位"
FROM "申请单风险信任评估明细" AS detail
LEFT JOIN "申请单基本信息" AS basic
    ON BTRIM(basic."单据编号") = BTRIM(detail."单据编号")
LEFT JOIN "人员属性查询" AS person
    ON BTRIM(person."工号") = BTRIM(basic."工号")
LEFT JOIN "组织属性查询" AS applicant_org
    ON BTRIM(applicant_org."行政组织编码") = BTRIM(person."部门ID")
LEFT JOIN "申请角色首行"
    ON "申请角色首行"."单据编号" = BTRIM(detail."单据编号")
   AND "申请角色首行"."角色编码" = BTRIM(detail."角色编码")
LEFT JOIN "权限列表" AS catalog
    ON BTRIM(catalog."角色编码") = BTRIM(detail."角色编码")
LEFT JOIN "组织属性查询" AS org
    ON BTRIM(org."行政组织编码") = BTRIM(detail."组织编码")
WHERE detail."是否低分明细" = TRUE;

CREATE OR REPLACE VIEW "申请单低分反馈预聚合视图" AS
WITH base AS (
    SELECT
        MD5(
            CONCAT_WS(
                '||',
                COALESCE(NULLIF(BTRIM("单据编号"), ''), '<NULL>'),
                COALESCE(NULLIF(BTRIM("评估批次号"), ''), '<NULL>'),
                COALESCE(NULLIF(BTRIM("维度名称"), ''), '<NULL>'),
                COALESCE(NULLIF(BTRIM("命中规则编码"), ''), '<NULL>'),
                COALESCE("维度得分"::TEXT, '<NULL>'),
                COALESCE(NULLIF(BTRIM(COALESCE("证据摘要", "命中规则说明", "明细结论")), ''), '<NULL>'),
                COALESCE(NULLIF(BTRIM("建议干预动作"), ''), '<NULL>'),
                COALESCE(NULLIF(BTRIM("申请人组织单位"), ''), '<NULL>'),
                COALESCE(NULLIF(BTRIM("目标组织单位"), ''), '<NULL>')
            )
        ) AS "分组键",
        *
    FROM "申请单低分明细富化视图"
),
grouped AS (
    SELECT
        "分组键",
        "单据编号",
        "评估批次号",
        "评估版本",
        "维度名称",
        "命中规则编码",
        "维度得分",
        COALESCE(NULLIF(BTRIM(COALESCE("证据摘要", "命中规则说明", "明细结论")), ''), '') AS "低分原因文案",
        COALESCE(NULLIF(BTRIM("建议干预动作"), ''), '') AS "建议干预动作",
        COALESCE(NULLIF(BTRIM("申请人组织单位"), ''), '') AS "申请人组织单位",
        COALESCE(NULLIF(BTRIM("目标组织单位"), ''), '') AS "目标组织单位",
        COUNT(*) AS "原始低分明细数",
        COUNT(DISTINCT NULLIF(BTRIM("组织编码"), '')) AS "影响组织数",
        COUNT(DISTINCT NULLIF(BTRIM("角色编码"), '')) AS "影响角色数"
    FROM base
    GROUP BY
        "分组键",
        "单据编号",
        "评估批次号",
        "评估版本",
        "维度名称",
        "命中规则编码",
        "维度得分",
        COALESCE(NULLIF(BTRIM(COALESCE("证据摘要", "命中规则说明", "明细结论")), ''), ''),
        COALESCE(NULLIF(BTRIM("建议干预动作"), ''), ''),
        COALESCE(NULLIF(BTRIM("申请人组织单位"), ''), ''),
        COALESCE(NULLIF(BTRIM("目标组织单位"), ''), '')
),
role_items AS (
    SELECT DISTINCT
        "分组键",
        BTRIM("角色编码") AS "角色编码",
        COALESCE(NULLIF(BTRIM("角色名称"), ''), NULLIF(BTRIM("角色编码"), '')) AS "角色名称",
        COALESCE(NULLIF(BTRIM("权限级别"), ''), '') AS "权限级别",
        COALESCE(NULLIF(BTRIM("明细行号"), ''), '') AS "明细行号"
    FROM base
    WHERE NULLIF(BTRIM("角色编码"), '') IS NOT NULL
),
org_items AS (
    SELECT DISTINCT
        "分组键",
        BTRIM("组织编码") AS "组织编码",
        COALESCE(NULLIF(BTRIM("行政组织名称"), ''), NULLIF(BTRIM("组织编码"), '')) AS "行政组织名称",
        COALESCE(NULLIF(BTRIM("物理层级"), ''), '') AS "物理层级"
    FROM base
    WHERE NULLIF(BTRIM("组织编码"), '') IS NOT NULL
)
SELECT
    grouped."分组键",
    grouped."单据编号",
    grouped."评估批次号",
    grouped."评估版本",
    grouped."维度名称",
    grouped."命中规则编码",
    grouped."维度得分",
    grouped."低分原因文案",
    grouped."建议干预动作",
    grouped."申请人组织单位",
    grouped."目标组织单位",
    grouped."原始低分明细数",
    grouped."影响组织数",
    grouped."影响角色数",
    COALESCE(
        (
            SELECT jsonb_agg(
                jsonb_build_object(
                    'role_code', role_items."角色编码",
                    'role_name', role_items."角色名称",
                    'permission_level', role_items."权限级别",
                    'line_no', role_items."明细行号"
                )
                ORDER BY role_items."角色编码", role_items."明细行号"
            )
            FROM role_items
            WHERE role_items."分组键" = grouped."分组键"
        ),
        '[]'::JSONB
    ) AS "角色列表",
    COALESCE(
        (
            SELECT jsonb_agg(
                jsonb_build_object(
                    'org_code', org_items."组织编码",
                    'organization_name', org_items."行政组织名称",
                    'physical_level', org_items."物理层级"
                )
                ORDER BY org_items."组织编码"
            )
            FROM org_items
            WHERE org_items."分组键" = grouped."分组键"
        ),
        '[]'::JSONB
    ) AS "组织列表"
FROM grouped;
