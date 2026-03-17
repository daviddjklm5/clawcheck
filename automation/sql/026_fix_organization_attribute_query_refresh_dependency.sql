-- 热修复：修正 refresh_组织属性查询() 的换表策略，避免依赖视图绑定到 __old 表后导致刷新失败。
-- 适用场景：已部署低分反馈相关视图后，执行组织列表导入或手动 SELECT refresh_组织属性查询() 失败。

BEGIN;

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

COMMIT;
