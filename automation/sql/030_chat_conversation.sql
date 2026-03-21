CREATE TABLE IF NOT EXISTS "对话会话" (
    "会话ID" TEXT PRIMARY KEY,
    "会话标题" TEXT NOT NULL,
    "工作目录" TEXT NOT NULL,
    "模型提供方" TEXT NOT NULL,
    "模型名称" TEXT NOT NULL,
    "状态" TEXT NOT NULL DEFAULT 'idle',
    "创建时间" TIMESTAMP NOT NULL DEFAULT NOW(),
    "最后活跃时间" TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS "对话消息" (
    "消息ID" TEXT PRIMARY KEY,
    "会话ID" TEXT NOT NULL REFERENCES "对话会话"("会话ID") ON DELETE CASCADE,
    "角色" TEXT NOT NULL,
    "消息内容" TEXT NOT NULL DEFAULT '',
    "token数量" INTEGER NULL,
    "创建时间" TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS "idx_对话消息_会话ID_创建时间"
ON "对话消息" ("会话ID", "创建时间");

CREATE TABLE IF NOT EXISTS "对话执行日志" (
    "日志ID" TEXT PRIMARY KEY,
    "会话ID" TEXT NOT NULL REFERENCES "对话会话"("会话ID") ON DELETE CASCADE,
    "消息ID" TEXT NULL REFERENCES "对话消息"("消息ID") ON DELETE SET NULL,
    "事件类型" TEXT NOT NULL,
    "事件摘要" TEXT NOT NULL,
    "退出码" INTEGER NULL,
    "创建时间" TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS "idx_对话执行日志_会话ID_创建时间"
ON "对话执行日志" ("会话ID", "创建时间");

