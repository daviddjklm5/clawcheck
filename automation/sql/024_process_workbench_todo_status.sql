DO $$
BEGIN
    IF to_regclass(format('%I.%I', current_schema(), '申请单基本信息')) IS NOT NULL THEN
        EXECUTE '
            ALTER TABLE "申请单基本信息"
            ADD COLUMN IF NOT EXISTS "待办处理状态" VARCHAR(32) NOT NULL DEFAULT ''待处理''
        ';

        EXECUTE '
            ALTER TABLE "申请单基本信息"
            ADD COLUMN IF NOT EXISTS "待办状态更新时间" TIMESTAMP NULL
        ';

        EXECUTE '
            UPDATE "申请单基本信息"
            SET "待办处理状态" = COALESCE(NULLIF(BTRIM("待办处理状态"), ''''), ''待处理''),
                "待办状态更新时间" = COALESCE("待办状态更新时间", "记录更新时间")
        ';

        EXECUTE '
            CREATE INDEX IF NOT EXISTS idx_apply_form_basic_info_todo_process_status
            ON "申请单基本信息"("待办处理状态")
        ';
    END IF;
END $$;
