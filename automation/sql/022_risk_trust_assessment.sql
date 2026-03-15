CREATE TABLE IF NOT EXISTS "申请单风险信任评估" (
    "评估ID" BIGSERIAL PRIMARY KEY,
    "单据编号" VARCHAR(64) NOT NULL REFERENCES "申请单基本信息"("单据编号") ON DELETE CASCADE,
    "评估批次号" VARCHAR(64) NOT NULL,
    "评估版本" VARCHAR(64) NOT NULL,
    "申请人HR类型" VARCHAR(8),
    "申请人组织流程层级分类" VARCHAR(64),
    "最终信任分" NUMERIC(3, 1) NOT NULL,
    "总结论" VARCHAR(32) NOT NULL,
    "建议动作" VARCHAR(32) NOT NULL,
    "最低命中维度" VARCHAR(64) NOT NULL,
    "最低命中角色编码" VARCHAR(128),
    "最低命中组织编码" VARCHAR(64),
    "是否命中人工干预" BOOLEAN NOT NULL DEFAULT FALSE,
    "是否存在低分明细" BOOLEAN NOT NULL DEFAULT FALSE,
    "低分明细条数" INTEGER NOT NULL DEFAULT 0,
    "低分明细结论" TEXT,
    "评估说明" TEXT,
    "输入快照" JSONB,
    "评估时间" TIMESTAMP NOT NULL DEFAULT NOW(),
    "记录创建时间" TIMESTAMP NOT NULL DEFAULT NOW(),
    "记录更新时间" TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_申请单风险信任评估_单据批次版本
ON "申请单风险信任评估"("单据编号", "评估批次号", "评估版本");

CREATE INDEX IF NOT EXISTS idx_申请单风险信任评估_总结论
ON "申请单风险信任评估"("总结论");

CREATE INDEX IF NOT EXISTS idx_申请单风险信任评估_建议动作
ON "申请单风险信任评估"("建议动作");

CREATE INDEX IF NOT EXISTS idx_申请单风险信任评估_最终信任分
ON "申请单风险信任评估"("最终信任分");

CREATE INDEX IF NOT EXISTS idx_申请单风险信任评估_评估批次号
ON "申请单风险信任评估"("评估批次号");

CREATE TABLE IF NOT EXISTS "申请单风险信任评估明细" (
    "评估明细ID" BIGSERIAL PRIMARY KEY,
    "单据编号" VARCHAR(64) NOT NULL REFERENCES "申请单基本信息"("单据编号") ON DELETE CASCADE,
    "评估批次号" VARCHAR(64) NOT NULL,
    "评估版本" VARCHAR(64) NOT NULL,
    "角色编码" VARCHAR(128),
    "角色名称" VARCHAR(255),
    "组织编码" VARCHAR(64),
    "维度名称" VARCHAR(64) NOT NULL,
    "命中规则编码" VARCHAR(128) NOT NULL,
    "命中规则说明" TEXT,
    "维度得分" NUMERIC(3, 1) NOT NULL,
    "明细结论" TEXT NOT NULL,
    "是否低分明细" BOOLEAN NOT NULL DEFAULT FALSE,
    "建议干预动作" VARCHAR(128),
    "证据摘要" TEXT,
    "证据快照" JSONB,
    "评估时间" TIMESTAMP NOT NULL DEFAULT NOW(),
    "记录创建时间" TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_申请单风险信任评估明细_单据编号
ON "申请单风险信任评估明细"("单据编号");

CREATE INDEX IF NOT EXISTS idx_申请单风险信任评估明细_评估批次号
ON "申请单风险信任评估明细"("评估批次号");

CREATE INDEX IF NOT EXISTS idx_申请单风险信任评估明细_角色编码
ON "申请单风险信任评估明细"("角色编码");

CREATE INDEX IF NOT EXISTS idx_申请单风险信任评估明细_组织编码
ON "申请单风险信任评估明细"("组织编码");

CREATE INDEX IF NOT EXISTS idx_申请单风险信任评估明细_维度名称
ON "申请单风险信任评估明细"("维度名称");

CREATE INDEX IF NOT EXISTS idx_申请单风险信任评估明细_维度得分
ON "申请单风险信任评估明细"("维度得分");

CREATE INDEX IF NOT EXISTS idx_申请单风险信任评估明细_是否低分明细
ON "申请单风险信任评估明细"("是否低分明细");
