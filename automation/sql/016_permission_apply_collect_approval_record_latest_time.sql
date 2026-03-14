DO $$
BEGIN
    IF to_regclass(format('%I.%I', current_schema(), '申请单基本信息')) IS NOT NULL THEN
        EXECUTE '
            ALTER TABLE "申请单基本信息"
            ADD COLUMN IF NOT EXISTS "最新审批时间" TIMESTAMP NULL
        ';
    END IF;

    IF to_regclass(format('%I.%I', current_schema(), '申请单审批记录')) IS NOT NULL THEN
        EXECUTE '
            ALTER TABLE "申请单审批记录"
            ADD COLUMN IF NOT EXISTS "工号" VARCHAR(64)
        ';

        EXECUTE $sql$
            UPDATE "申请单审批记录"
            SET
                "工号" = COALESCE(
                    NULLIF("工号", ''),
                    NULLIF(substring("审批人" from '[\(（]([0-9]+)[\)）]'), '')
                ),
                "审批人" = btrim(regexp_replace("审批人", '[\(（][0-9]+[\)）]$', ''))
            WHERE "审批人" ~ '[\(（][0-9]+[\)）]$'
        $sql$;

        IF to_regclass(format('%I.%I', current_schema(), '在职花名册表')) IS NOT NULL THEN
            EXECUTE $sql$
                WITH unique_roster AS (
                    SELECT "姓名", MIN("人员编号") AS "人员编号"
                    FROM "在职花名册表"
                    WHERE "姓名" IS NOT NULL
                      AND "人员编号" IS NOT NULL
                    GROUP BY "姓名"
                    HAVING COUNT(DISTINCT "人员编号") = 1
                )
                UPDATE "申请单审批记录" ar
                SET "工号" = ur."人员编号"
                FROM unique_roster ur
                WHERE ar."审批人" = ur."姓名"
                  AND COALESCE(ar."工号", '') = ''
            $sql$;
        END IF;

        EXECUTE $sql$
            DELETE FROM "申请单审批记录"
            WHERE regexp_replace(COALESCE("原始展示文本", ''), '\s+', ' ', 'g')
                = '属地人力资源部负责人 通过规则：全部通过'
        $sql$;

        EXECUTE $sql$
            WITH renumbered AS (
                SELECT
                    "审批记录ID",
                    ROW_NUMBER() OVER (
                        PARTITION BY "单据编号"
                        ORDER BY
                            CASE WHEN "审批记录顺序号" IS NULL THEN 1 ELSE 0 END,
                            "审批记录顺序号",
                            "审批记录ID"
                    ) AS new_record_seq
                FROM "申请单审批记录"
            )
            UPDATE "申请单审批记录" ar
            SET "审批记录顺序号" = renumbered.new_record_seq
            FROM renumbered
            WHERE ar."审批记录ID" = renumbered."审批记录ID"
        $sql$;
    END IF;

    IF
        to_regclass(format('%I.%I', current_schema(), '申请单基本信息')) IS NOT NULL
        AND to_regclass(format('%I.%I', current_schema(), '申请单审批记录')) IS NOT NULL
    THEN
        EXECUTE 'UPDATE "申请单基本信息" SET "最新审批时间" = NULL';

        EXECUTE $sql$
            WITH latest_record AS (
                SELECT DISTINCT ON ("单据编号")
                    "单据编号",
                    "审批时间"
                FROM "申请单审批记录"
                ORDER BY
                    "单据编号",
                    CASE WHEN "审批记录顺序号" IS NULL THEN 1 ELSE 0 END,
                    "审批记录顺序号" DESC,
                    "审批记录ID" DESC
            )
            UPDATE "申请单基本信息" bi
            SET "最新审批时间" = lr."审批时间"
            FROM latest_record lr
            WHERE bi."单据编号" = lr."单据编号"
        $sql$;
    END IF;
END $$;
