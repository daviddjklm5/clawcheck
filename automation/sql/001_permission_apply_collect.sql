CREATE TABLE IF NOT EXISTS "申请单基本信息" (
    "单据编号" VARCHAR(64) PRIMARY KEY,
    "工号" VARCHAR(64) NOT NULL,
    "权限对象" VARCHAR(128) NOT NULL,
    "申请理由" TEXT,
    "单据状态" VARCHAR(64),
    "人事管理组织" VARCHAR(128),
    "公司" VARCHAR(128),
    "部门" VARCHAR(128),
    "职位" VARCHAR(128),
    "申请日期" TIMESTAMP NULL,
    "最新审批时间" TIMESTAMP NULL,
    "采集次数" INTEGER NOT NULL DEFAULT 1,
    "待办处理状态" VARCHAR(32) NOT NULL DEFAULT '待处理',
    "待办状态更新时间" TIMESTAMP NULL,
    "记录创建时间" TIMESTAMP NOT NULL DEFAULT NOW(),
    "记录更新时间" TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS "申请单权限列表" (
    "权限明细ID" BIGSERIAL PRIMARY KEY,
    "单据编号" VARCHAR(64) NOT NULL REFERENCES "申请单基本信息"("单据编号") ON DELETE CASCADE,
    "明细行号" VARCHAR(32),
    "申请类型" VARCHAR(128),
    "角色名称" VARCHAR(255),
    "角色描述" TEXT,
    "角色编码" VARCHAR(128),
    "参保单位" TEXT,
    "组织范围数量" INTEGER,
    "记录创建时间" TIMESTAMP NOT NULL DEFAULT NOW(),
    "记录更新时间" TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_apply_form_permission_list UNIQUE ("单据编号", "明细行号")
);

CREATE TABLE IF NOT EXISTS "申请单审批记录" (
    "审批记录ID" BIGSERIAL PRIMARY KEY,
    "单据编号" VARCHAR(64) NOT NULL REFERENCES "申请单基本信息"("单据编号") ON DELETE CASCADE,
    "审批记录顺序号" INTEGER,
    "节点名称" VARCHAR(128),
    "审批人" VARCHAR(128),
    "工号" VARCHAR(64),
    "审批人组织或职位" VARCHAR(255),
    "审批动作" VARCHAR(64),
    "审批意见" TEXT,
    "审批时间" TIMESTAMP NULL,
    "原始展示文本" TEXT,
    "记录创建时间" TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS "申请表组织范围" (
    "组织范围ID" BIGSERIAL PRIMARY KEY,
    "单据编号" VARCHAR(64) NOT NULL REFERENCES "申请单基本信息"("单据编号") ON DELETE CASCADE,
    "角色编码" VARCHAR(128) NOT NULL,
    "角色名称" VARCHAR(255) NOT NULL,
    "组织编码" VARCHAR(64),
    "记录创建时间" TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_apply_form_permission_list_document_no ON "申请单权限列表"("单据编号");
CREATE INDEX IF NOT EXISTS idx_apply_form_approval_record_document_no ON "申请单审批记录"("单据编号");
CREATE INDEX IF NOT EXISTS idx_apply_form_org_scope_document_no ON "申请表组织范围"("单据编号");
CREATE INDEX IF NOT EXISTS idx_apply_form_org_scope_role_code ON "申请表组织范围"("角色编码");
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = '申请单基本信息'
          AND column_name = '工号'
    ) THEN
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_apply_form_basic_info_employee_no ON "申请单基本信息"("工号")';
    END IF;
END $$;
CREATE INDEX IF NOT EXISTS idx_apply_form_basic_info_todo_process_status ON "申请单基本信息"("待办处理状态");
CREATE UNIQUE INDEX IF NOT EXISTS uq_apply_form_org_scope_doc_role_org
ON "申请表组织范围"("单据编号", "角色编码", "组织编码")
WHERE "组织编码" IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_apply_form_org_scope_doc_role_null_org
ON "申请表组织范围"("单据编号", "角色编码")
WHERE "组织编码" IS NULL;
