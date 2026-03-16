INSERT INTO "权限列表" (
    "角色编码",
    "角色名称",
    "权限级别",
    "不检查组织范围",
    "数据来源",
    "原始快照",
    "记录创建时间",
    "记录更新时间"
)
VALUES (
    'qbireport',
    'QBI报表权限申请',
    'C类-常规',
    TRUE,
    'manual_seed',
    jsonb_build_object(
        'role_code', 'qbireport',
        'role_name', 'QBI报表权限申请',
        'permission_level', 'C类-常规',
        'skip_org_scope_check', true,
        'change_ticket', 'QBI报表权限申请不检查组织范围'
    ),
    NOW(),
    NOW()
)
ON CONFLICT ("角色编码") DO UPDATE
SET "角色名称" = EXCLUDED."角色名称",
    "权限级别" = COALESCE(NULLIF("权限列表"."权限级别", ''), EXCLUDED."权限级别"),
    "不检查组织范围" = TRUE,
    "数据来源" = EXCLUDED."数据来源",
    "原始快照" = EXCLUDED."原始快照",
    "记录更新时间" = NOW();
