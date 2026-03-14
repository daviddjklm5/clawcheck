DO $$
BEGIN
    IF to_regclass(format('%I.%I', current_schema(), '申请表组织范围')) IS NULL THEN
        RETURN;
    END IF;

    ALTER TABLE "申请表组织范围"
        ADD COLUMN IF NOT EXISTS "角色编码" VARCHAR(128),
        ADD COLUMN IF NOT EXISTS "角色名称" VARCHAR(255);

    ALTER TABLE "申请表组织范围"
        ALTER COLUMN "组织编码" DROP NOT NULL;

    ALTER TABLE "申请表组织范围"
        DROP CONSTRAINT IF EXISTS uq_apply_form_org_scope;

    DELETE FROM "申请表组织范围"
    WHERE "角色编码" IS NULL
       OR "角色名称" IS NULL;

    ALTER TABLE "申请表组织范围"
        ALTER COLUMN "角色编码" SET NOT NULL,
        ALTER COLUMN "角色名称" SET NOT NULL;

    CREATE INDEX IF NOT EXISTS idx_apply_form_org_scope_document_no
        ON "申请表组织范围" ("单据编号");

    CREATE INDEX IF NOT EXISTS idx_apply_form_org_scope_role_code
        ON "申请表组织范围" ("角色编码");

    CREATE UNIQUE INDEX IF NOT EXISTS uq_apply_form_org_scope_doc_role_org
        ON "申请表组织范围" ("单据编号", "角色编码", "组织编码")
        WHERE "组织编码" IS NOT NULL;

    CREATE UNIQUE INDEX IF NOT EXISTS uq_apply_form_org_scope_doc_role_null_org
        ON "申请表组织范围" ("单据编号", "角色编码")
        WHERE "组织编码" IS NULL;
END $$;
