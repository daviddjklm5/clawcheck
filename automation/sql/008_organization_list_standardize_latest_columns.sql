ALTER TABLE IF EXISTS "组织列表"
    ADD COLUMN IF NOT EXISTS established_date TEXT,
    ADD COLUMN IF NOT EXISTS business_status TEXT,
    ADD COLUMN IF NOT EXISTS org_function TEXT,
    ADD COLUMN IF NOT EXISTS work_location TEXT,
    ADD COLUMN IF NOT EXISTS pending_disable_date TEXT,
    ADD COLUMN IF NOT EXISTS department_type TEXT,
    ADD COLUMN IF NOT EXISTS org_created_time TEXT;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = '组织列表'
          AND column_name = '成立日期'
    ) THEN
        EXECUTE 'UPDATE "组织列表" SET established_date = COALESCE(established_date, "成立日期") WHERE established_date IS NULL';
        EXECUTE 'ALTER TABLE "组织列表" DROP COLUMN IF EXISTS "成立日期"';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = '组织列表'
          AND column_name = '业务状态'
    ) THEN
        EXECUTE 'UPDATE "组织列表" SET business_status = COALESCE(business_status, "业务状态") WHERE business_status IS NULL';
        EXECUTE 'ALTER TABLE "组织列表" DROP COLUMN IF EXISTS "业务状态"';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = '组织列表'
          AND column_name = '行政组织职能'
    ) THEN
        EXECUTE 'UPDATE "组织列表" SET org_function = COALESCE(org_function, "行政组织职能") WHERE org_function IS NULL';
        EXECUTE 'ALTER TABLE "组织列表" DROP COLUMN IF EXISTS "行政组织职能"';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = '组织列表'
          AND column_name = '工作地'
    ) THEN
        EXECUTE 'UPDATE "组织列表" SET work_location = COALESCE(work_location, "工作地") WHERE work_location IS NULL';
        EXECUTE 'ALTER TABLE "组织列表" DROP COLUMN IF EXISTS "工作地"';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = '组织列表'
          AND column_name = '待停用日期'
    ) THEN
        EXECUTE 'UPDATE "组织列表" SET pending_disable_date = COALESCE(pending_disable_date, "待停用日期") WHERE pending_disable_date IS NULL';
        EXECUTE 'ALTER TABLE "组织列表" DROP COLUMN IF EXISTS "待停用日期"';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = '组织列表'
          AND column_name = '部门类型'
    ) THEN
        EXECUTE 'UPDATE "组织列表" SET department_type = COALESCE(department_type, "部门类型") WHERE department_type IS NULL';
        EXECUTE 'ALTER TABLE "组织列表" DROP COLUMN IF EXISTS "部门类型"';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = '组织列表'
          AND column_name = '创建时间'
    ) THEN
        EXECUTE 'UPDATE "组织列表" SET org_created_time = COALESCE(org_created_time, "创建时间") WHERE org_created_time IS NULL';
        EXECUTE 'ALTER TABLE "组织列表" DROP COLUMN IF EXISTS "创建时间"';
    END IF;
END;
$$;
