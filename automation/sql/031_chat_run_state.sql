CREATE TABLE IF NOT EXISTS "对话运行状态" (
    "运行ID" TEXT PRIMARY KEY,
    "会话ID" TEXT NOT NULL REFERENCES "对话会话"("会话ID") ON DELETE CASCADE,
    "状态" TEXT NOT NULL,
    "执行模式" TEXT NOT NULL,
    "workerID" TEXT NOT NULL DEFAULT '',
    "错误码" TEXT NOT NULL DEFAULT '',
    "错误信息" TEXT NOT NULL DEFAULT '',
    "开始时间" TIMESTAMP NULL,
    "更新时间" TIMESTAMP NOT NULL DEFAULT NOW(),
    "结束时间" TIMESTAMP NULL,
    "创建时间" TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS "idx_对话运行状态_会话ID_更新时间"
ON "对话运行状态" ("会话ID", "更新时间");

CREATE INDEX IF NOT EXISTS "idx_对话运行状态_状态_更新时间"
ON "对话运行状态" ("状态", "更新时间");

