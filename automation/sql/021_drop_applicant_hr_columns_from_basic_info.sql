DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = current_schema()
          AND table_name = '申请单基本信息'
    ) THEN
        RETURN;
    END IF;

    DROP INDEX IF EXISTS idx_apply_form_basic_info_hr_type;

    ALTER TABLE "申请单基本信息"
    DROP COLUMN IF EXISTS "花名册匹配状态",
    DROP COLUMN IF EXISTS "申请人HR类型",
    DROP COLUMN IF EXISTS "是否责任HR",
    DROP COLUMN IF EXISTS "是否HR人员",
    DROP COLUMN IF EXISTS "是否疑似HR人员",
    DROP COLUMN IF EXISTS "HR主判定依据",
    DROP COLUMN IF EXISTS "HR主判定值",
    DROP COLUMN IF EXISTS "HR子域",
    DROP COLUMN IF EXISTS "HR判定原因";
END $$;
