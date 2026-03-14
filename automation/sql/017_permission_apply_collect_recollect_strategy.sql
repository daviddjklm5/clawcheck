DO $$
BEGIN
    IF to_regclass(format('%I.%I', current_schema(), '申请单基本信息')) IS NOT NULL THEN
        EXECUTE '
            ALTER TABLE "申请单基本信息"
            ADD COLUMN IF NOT EXISTS "采集次数" INTEGER NOT NULL DEFAULT 1
        ';

        EXECUTE '
            UPDATE "申请单基本信息"
            SET "采集次数" = 1
            WHERE "采集次数" IS NULL
        ';
    END IF;
END $$;
