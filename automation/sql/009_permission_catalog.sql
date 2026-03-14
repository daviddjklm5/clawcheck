CREATE TABLE IF NOT EXISTS "权限列表" (
    role_code VARCHAR(64) PRIMARY KEY,
    role_name VARCHAR(255) NOT NULL,
    permission_level VARCHAR(64) NOT NULL,
    role_group VARCHAR(16) NOT NULL,
    is_remote_role BOOLEAN NOT NULL DEFAULT FALSE,
    "不检查组织范围" BOOLEAN NOT NULL DEFAULT FALSE,
    is_deprecated BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    source_system VARCHAR(32) NOT NULL DEFAULT 'manual_seed',
    raw_payload JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

ALTER TABLE "权限列表"
    ADD COLUMN IF NOT EXISTS "不检查组织范围" BOOLEAN NOT NULL DEFAULT FALSE;

WITH seed_data(role_code, role_name, permission_level, sort_order) AS (
    VALUES
        ('QB001', 'BP（查看）', 'B1类-涉薪', 1),
        ('HMC003', '花名册薪酬版', 'B1类-涉薪', 2),
        ('EP002', 'EP查看', 'S2类-限定', 3),
        ('RCJL003', '人才履历薪酬版', 'B1类-涉薪', 4),
        ('RLLZ002', '离职补偿金', 'B1类-涉薪', 5),
        ('DTX002', '调薪申请', 'B1类-涉薪', 6),
        ('DTX003', '定调薪档案/定调薪明细', 'B1类-涉薪', 7),
        ('DTX005', '业薪数据/工资表', 'B1类-涉薪', 8),
        ('DTX006', '个税', 'B1类-涉薪', 9),
        ('EP001', 'EP维护', 'S1类-限定', 10),
        ('QF24', '远程薪酬主管', 'A类-远程', 11),
        ('QF25', '远程薪酬', 'A类-远程', 12),
        ('JX001', '绩效共享BP', 'B2类-涉档案绩效', 13),
        ('YG002', '人员档案-可查看引出-无定薪有绩效', 'B2类-涉档案绩效', 14),
        ('HMC002', '花名册绩效版', 'B2类-涉档案绩效', 15),
        ('DTX001', '定薪申请', 'B1类-涉薪', 16),
        ('QF19', '远程人事运营主管', 'A类-远程', 17),
        ('QF20', '远程人事运营（转任调）', 'A类-远程', 18),
        ('QF21', '远程人事运营岗（信息）', 'A类-远程', 19),
        ('QF30', '远程人事运营（组织岗位维护）', 'A类-远程', 20),
        ('RLRZ003', '入职申请-远程', 'A类-远程', 21),
        ('ZZ002', '建岗', 'A类-远程', 22),
        ('RLHT003', '劳动合同/协议续签（可提交）/改签', 'A类-远程', 23),
        ('DTX004', '定薪审核', 'A类-远程', 24),
        ('DTX010', '转正调薪审核', 'A类-远程', 25),
        ('YG004', '人员档案-可查看引出引入-无定薪有绩效', 'A类-远程', 26),
        ('YG005', '人员档案-可查看引出引入-无定薪无绩效', 'A类-远程', 27),
        ('RLHMD002', '黑名单维护', 'A类-远程', 28),
        ('SS001', '远程社保岗', 'A类-远程', 29),
        ('SS003', '远程社保岗组长', 'A类-远程', 30),
        ('JQ002', '考勤核算（定额新增）', 'A类-远程', 31),
        ('WY32', '定岗定薪HR', 'W类-取消', 32),
        ('WY30', '项目HR（有薪酬）', 'W类-取消', 33),
        ('WY35', '定岗定薪HR（上传资料）', 'W类-取消', 34),
        ('WY62', '（万御安防）定岗定薪-新', 'W类-取消', 35),
        ('WY64', '（万御安防）转调离（含调薪）', 'W类-取消', 36),
        ('WY63', '（万御安防）转调离（不含调薪）', 'W类-取消', 37),
        ('BB001', '离职率报表', 'B2类-涉档案绩效', 38),
        ('FD001', '福袋查询', 'C类-常规', 39),
        ('FD002', '福袋新增', 'C类-常规', 40),
        ('HBGX001', '汇报关系维护-临时角色', 'C类-常规', 41),
        ('HMC001', '花名册基础版', 'B2类-涉档案绩效', 42),
        ('JQ001', '考勤核算', 'C类-常规', 43),
        ('JX004', '绩效业务BP', 'B2类-涉档案绩效', 44),
        ('QB002', '入转调离查看', 'B2类-涉档案绩效', 45),
        ('RCJL002', '人才履历人才版', 'B2类-涉档案绩效', 46),
        ('RLDD002', '调动申请', 'C类-常规', 47),
        ('RLHMD001', '黑名单查看', 'C类-常规', 48),
        ('RLHT001', '劳动合同/协议新签', 'B2类-涉档案绩效', 49),
        ('RLHT002', '劳动合同/协议续签/改签', 'B2类-涉档案绩效', 50),
        ('RLLZ001', '离职申请', 'C类-常规', 51),
        ('RLRZ001', '入职申请-非万御', 'C类-常规', 52),
        ('RLRZ002', '入职申请-万御', 'C类-常规', 53),
        ('RLZZ001', '转正申请', 'C类-常规', 54),
        ('SS002', '属地社保岗', 'B1类-涉薪', 55),
        ('YDZZ001', '异地工作支持申请', 'B1类-涉薪', 56),
        ('YG003', '人员档案-可查看引出-无定薪无绩效', 'B2类-涉档案绩效', 57),
        ('YZH001', 'AD域管理', 'C类-常规', 58),
        ('YZH002', '短期驻场管理', 'C类-常规', 59),
        ('ZZ001', '组织/岗位查看', 'C类-常规', 60),
        ('DTX009', '业务数据提报', 'C类-常规', 61),
        ('DY-001', '党员管理员', 'S1类-限定', 62),
        ('QF_renmian_001', '远程人事运营岗(任免岗)', 'A类-远程', 63),
        ('QF_xinxi_001', '远程人事运营岗（信息岗）', 'A类-远程', 64),
        ('QF_zhuandiao_001', '远程人事运营岗(转调岗)', 'A类-远程', 65),
        ('RCJL001', '人才履历基础版', 'B2类-涉档案绩效', 66),
        ('RCPD001', '人才盘点报表', 'B2类-涉档案绩效', 67),
        ('RXFP_001', '退休管理', 'B1类-涉薪', 68),
        ('YG001', '人员档案-可查看引出-有定薪有绩效', 'B1类-涉薪', 69),
        ('ZZ005', '岗位COE', 'S1类-限定', 70),
        ('pxrz1', '培训认证信息查看', 'C类-常规', 71),
        ('WY74', '（万物云其他军种）转正维护', 'W类-取消', 72),
        ('WB03', '（万物云其他军种）转正维护-2', 'W类-取消', 73),
        ('WA01', '（万御安防）-“一个人”权限包', 'W类-取消', 74),
        ('WB01', '（万物云其他军种）-“一个人”权限包', 'W类-取消', 75),
        ('WY42', '缺勤定额报表', 'W类-取消', 76),
        ('WA04', '（万御安防）转调离（含调薪）-2', 'W类-取消', 77),
        ('WY33', '项目HR（无薪酬）', 'W类-取消', 78),
        ('WY21', '公司HRBP（无薪酬、含绩效）', 'W类-取消', 79),
        ('WY73', '（万物云其他军种）定岗定薪-新', 'W类-取消', 80),
        ('WY20', '公司HRBP（薪酬）', 'W类-取消', 81),
        ('WC01', '公司HRBP（薪酬）1', 'W类-取消', 82),
        ('WC07', '公司HR负责人2', 'W类-取消', 83),
        ('WC02', '项目HR（有薪酬）1', 'W类-取消', 84),
        ('WY18', '公司运营专员HR', 'W类-取消', 85),
        ('WY24', '公司招聘HR', 'W类-取消', 86),
        ('WB04', '（万物云其他军种）调动维护-2', 'W类-取消', 87),
        ('WC05', '项目HR（无薪酬）1', 'W类-取消', 88),
        ('WA03', '（万御安防）转调离（不含调薪）-2', 'W类-取消', 89),
        ('WB05', '（万物云其他军种）离司维护-2', 'W类-取消', 90),
        ('WA02-1', '（万御安防）定岗定薪-新-2', 'W类-取消', 91),
        ('WY40', '组织机构查看', 'W类-取消', 92),
        ('WY26', '公司考勤HR', 'W类-取消', 93),
        ('WY75', '（万物云其他军种）调动维护', 'W类-取消', 94),
        ('WY45', '批量电子合同001', 'W类-取消', 95),
        ('WY72', '（万物云其他军种）离司维护', 'W类-取消', 96)
)
INSERT INTO "权限列表" (
    role_code,
    role_name,
    permission_level,
    role_group,
    is_remote_role,
    "不检查组织范围",
    is_deprecated,
    is_active,
    source_system,
    raw_payload,
    created_at,
    updated_at
)
SELECT
    role_code,
    role_name,
    permission_level,
    CASE
        WHEN permission_level LIKE 'A类-%' THEN 'A'
        WHEN permission_level LIKE 'B1类-%' THEN 'B1'
        WHEN permission_level LIKE 'B2类-%' THEN 'B2'
        WHEN permission_level LIKE 'C类-%' THEN 'C'
        WHEN permission_level LIKE 'S1类-%' THEN 'S1'
        WHEN permission_level LIKE 'S2类-%' THEN 'S2'
        WHEN permission_level LIKE 'W类-%' THEN 'W'
        ELSE 'UNKNOWN'
    END AS role_group,
    permission_level = 'A类-远程' AS is_remote_role,
    role_code IN ('RLHMD001', 'DTX009') AS "不检查组织范围",
    permission_level = 'W类-取消' AS is_deprecated,
    permission_level <> 'W类-取消' AS is_active,
    'manual_seed' AS source_system,
    jsonb_build_object(
        'role_code', role_code,
        'role_name', role_name,
        'permission_level', permission_level,
        'sort_order', sort_order
    ) AS raw_payload,
    NOW() AS created_at,
    NOW() AS updated_at
FROM seed_data
ON CONFLICT (role_code) DO UPDATE
SET role_name = EXCLUDED.role_name,
    permission_level = EXCLUDED.permission_level,
    role_group = EXCLUDED.role_group,
    is_remote_role = EXCLUDED.is_remote_role,
    "不检查组织范围" = EXCLUDED."不检查组织范围",
    is_deprecated = EXCLUDED.is_deprecated,
    is_active = EXCLUDED.is_active,
    source_system = EXCLUDED.source_system,
    raw_payload = EXCLUDED.raw_payload,
    updated_at = NOW();

CREATE INDEX IF NOT EXISTS "idx_权限列表_permission_level"
    ON "权限列表"(permission_level);

CREATE INDEX IF NOT EXISTS "idx_权限列表_role_group"
    ON "权限列表"(role_group);

CREATE INDEX IF NOT EXISTS "idx_权限列表_is_active"
    ON "权限列表"(is_active);
