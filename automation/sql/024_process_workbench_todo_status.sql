DO $$
DECLARE
    has_todo_process_status BOOLEAN;
    has_todo_status_updated_at BOOLEAN;
    has_todo_process_status_index BOOLEAN;
BEGIN
    IF to_regclass(format('%I.%I', current_schema(), '申请单基本信息')) IS NOT NULL THEN
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = '申请单基本信息'
              AND column_name = '待办处理状态'
        )
        INTO has_todo_process_status;

        IF NOT has_todo_process_status THEN
            EXECUTE '
                ALTER TABLE "申请单基本信息"
                ADD COLUMN "待办处理状态" VARCHAR(32) NOT NULL DEFAULT ''待处理''
            ';
            has_todo_process_status := TRUE;
        END IF;

        SELECT EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = '申请单基本信息'
              AND column_name = '待办状态更新时间'
        )
        INTO has_todo_status_updated_at;

        IF NOT has_todo_status_updated_at THEN
            EXECUTE '
                ALTER TABLE "申请单基本信息"
                ADD COLUMN "待办状态更新时间" TIMESTAMP NULL
            ';
            has_todo_status_updated_at := TRUE;
        END IF;

        IF has_todo_process_status AND has_todo_status_updated_at THEN
            EXECUTE '
                UPDATE "申请单基本信息"
                SET "待办处理状态" = COALESCE(NULLIF(BTRIM("待办处理状态"), ''''), ''待处理''),
                    "待办状态更新时间" = COALESCE("待办状态更新时间", "记录更新时间")
                WHERE "待办处理状态" IS NULL
                   OR BTRIM("待办处理状态") = ''''
                   OR "待办状态更新时间" IS NULL
            ';
        END IF;

        SELECT EXISTS (
            SELECT 1
            FROM pg_indexes
            WHERE schemaname = current_schema()
              AND indexname = 'idx_apply_form_basic_info_todo_process_status'
        )
        INTO has_todo_process_status_index;

        IF has_todo_process_status AND NOT has_todo_process_status_index THEN
            EXECUTE '
                CREATE INDEX idx_apply_form_basic_info_todo_process_status
                ON "申请单基本信息"("待办处理状态")
            ';
        END IF;
    END IF;
END $$;
