# 方案编号010：申请单申请人HR与疑似HR识别方案文档

## 1. 方案目标
基于 `申请单基本信息` 中的申请人工号，从 `在职花名册表` 匹配员工主数据，并结合以下字段判断申请人属于哪一类 HR 身份：

- `一级职能名称`
- `二级职能名称`
- `职位名称`
- `标准岗位名称`
- `组织路径名称`

本方案目标：
- 建立一套可执行的 `H1 / H2 / H3 / HX` 分类口径
- 将“明确 HR”“推定 HR”“疑似 HR”“不是 HR”分层处理
- 避免把挂在人力组织下的行政、法务、司机、PMO、运营等岗位直接误判为 HR
- 为后续规则引擎输出稳定、可解释、可扩展的申请人身份标签

本方案明确采用“**职位**”，不采用“职务”字段作为判定主依据。

## 2. 分类定义

### 2.1 最终分类
本方案建议将申请人 HR 判断分为 4 类：

- `H1`
  - 可以直接判断为 HR
  - 即当前已有明确信号规则可直接命中
- `H2`
  - 推定为 HR
  - 即当前在弱信号样本中，经调查后可单独提升为 HR 的职位
- `H3`
  - 疑似 HR
  - 当前存在 HR 弱信号，但证据不足，待后续继续补充规则
- `HX`
  - 不是 HR

### 2.2 未匹配花名册的处理
`H1 / H2 / H3 / HX` 建议仅用于**成功匹配花名册**的申请人。

若申请人工号未匹配到 `在职花名册表`，建议：
- `roster_match_status = UNMATCHED`
- `hr_type = NULL`

不建议把“未匹配花名册”直接归为 `HX`，原因如下：
- 未匹配不等于不是 HR
- 可能是花名册快照缺失、工号口径差异、历史人员或数据同步延迟

如业务侧强制要求四分类落表，可临时记为：
- `hr_type = HX`
- 同时保留 `hr_judgement_reason = roster_not_found`

## 3. 数据基础与实际分析结果

### 3.1 本次分析数据
本次分析基于本地 PostgreSQL 中的真实花名册数据：
- 花名册表：`在职花名册表`
- 数据量：`154,849` 人
- 花名册快照日期：`2026-03-11`

同时核对了当前申请单主表现状：
- 当前数据库中的物理表名仍是 `basic_info`
- 当前仅有 `1` 条申请单主表记录
- 该记录的 `employee_no` 未匹配到当前花名册

因此，本方案的判定口径主要依据**全量花名册分布分析**得出，而不是依据当前申请单样本。

### 3.2 关键字段完整度
`在职花名册表` 中与本方案相关字段的可用情况如下：

- `一级职能名称`：`152,492`
- `二级职能名称`：`152,492`
- `职位名称`：`154,849`
- `标准岗位名称`：`152,492`
- `组织路径名称`：`154,849`

结论：
- `一级职能名称`、`二级职能名称`、`标准岗位名称` 完整度较高，可作为主要判定字段
- `职位名称`、`组织路径名称` 基本全量可用
- `职务` 字段本次不纳入主判定逻辑

### 3.3 H1 强信号分析
基于真实数据统计，得到以下事实：

- `一级职能名称 = 人力资源`：`3,492` 人
- `职位名称` 命中 `人力 / 人事 / HR / HRBP` 等显式关键词：`2,334` 人
- `标准岗位名称` 命中 `人力 / 人事 / HR / HRBP` 等显式关键词：`2,723` 人

按当前 H1 口径：
- `一级职能名称 = 人力资源`
- 或 `职位名称` 明确命中 HR 关键词
- 或 `标准岗位名称` 明确命中 HR 关键词

则可识别出 `H1` 共 `3,565` 人。

### 3.4 二级职能分析结果
在 `一级职能名称 = 人力资源` 的 `3,492` 人中，`二级职能名称` 分布如下：

- `人力资源`：`1,388`
- `人事运营`：`1,246`
- `招聘`：`430`
- `薪酬绩效`：`144`
- `人才发展`：`141`
- `员工关系`：`87`
- `人力业务支持`：`35`
- `招聘外包服务`：`16`
- `组织发展`：`5`

同时还发现：
- 在 `一级职能名称 = 人力资源` 的人群中，有 `790` 人虽然 `职位名称` / `标准岗位名称` 没有显式出现 `人力 / 人事 / HR`，但其 `二级职能名称` 明确属于 HR 子域
- 这批人典型职位包括：`招聘专员`、`招聘配置`、`员工关系专员`、`人才发展`、`薪酬福利` 等

结论：
- `二级职能名称` 对于**解释 HR 内部子域**非常有价值
- 但在当前数据中，`二级职能名称` 没有单独新增识别出额外 HR 人员
- 因此 `二级职能名称` 适合作为解释字段，不建议在当前版本单独作为 H1 / H2 / H3 的主判定条件

### 3.5 弱信号分析
若仅使用 `组织路径名称` 中包含 `人力 / 人事 / HR` 作为判定条件，会命中一批弱信号人员。

在去除 H1 强信号后，这批弱信号人员共 `120` 人，其中：
- `H2`：`5` 人
- `H3`：`115` 人

弱信号人群中，抽样确认存在以下明显非 HR 岗位：
- `运营经理`
- `运营主管`
- `法务`
- `司机`
- `PMO`
- `廉正监察专家`
- `数据分析`

这说明：
- `组织路径名称` 不能直接把所有弱信号人群判成 HR
- 但弱信号中也可能存在应当提升为 HR 的少量岗位，需要单独抽取并固化成 `H2`

## 4. H1 / H2 / H3 / HX 判定口径

### 4.1 第一步：按工号匹配花名册
建议使用：
- `申请单基本信息.employee_no`
- 关联 `在职花名册表.employee_no`

匹配口径建议：
- 两侧都做 `BTRIM`
- 保持文本型，不转数值，避免前导零丢失

若未匹配到花名册，则：
- `roster_match_status = UNMATCHED`
- `hr_type = NULL`
- `hr_judgement_reason = roster_not_found`

### 4.2 H1：可以直接判断为 HR
满足任一条件即可判为 `H1`：

1. `一级职能名称 = 人力资源`
2. `职位名称` 明确命中 HR 关键词
3. `标准岗位名称` 明确命中 HR 关键词

建议首版 H1 显式关键词口径采用保守规则，优先识别以下显式文本：
- `人力`
- `人事`
- `HRBP`
- `HR共享`
- `业务HR`
- `项目HR`
- `综合人事`
- `人力资源`
- `人力行政`
- `人力业务支持`

这样设计的原因：
- 可直接识别 `HRBP`、`人事运营`、`人力资源岗`、`人力综合管理`、`人事远程交付中心总经理` 等明确 HR 身份
- 不会因为 `招聘`、`培训`、`人才发展` 等词出现在非 HR 职位里而误放大人群

### 4.3 H2：推定为 HR
`H2` 的定义是：
- 当前不满足 H1
- 但位于 HR 弱信号人群中
- 且经专项调查后，某些职位应从弱信号提升为“推定 HR”

当前版本先纳入以下 `职位名称`：
- `运营经理`
- `运营主管`
- `数据分析`

并且必须同时满足：
1. 不满足 H1
2. `组织路径名称` 包含 `人力`、`人事` 或 `HR`
3. `职位名称` 属于上述 H2 白名单

当前调查结果中，H2 共 `5` 人，样本包括：
- `数据分析`
  - `万物云_万科物业_人力资源与行政服务部`
- `运营主管`
  - `万物云_祥盈企服_远程交付中心_人事远程交付中心_数据服务组`
- `运营主管`
  - `万物云_祥盈企服_远程交付中心_人事远程交付中心_产品运营组_灵活用工组_A产品交付组`
- `运营经理`
  - `万物云_万物云城_高投城资_C人力资源与行政服务部`
- `运营经理`
  - `万物云_福建战区代表处_K厦门联美万誉_K人力行政部-联美万誉`

说明：
- H2 是“经人工调查后提升”的职位型规则
- 当前 H2 仅覆盖已调查确认的弱信号岗位
- 后续若发现更多应提升岗位，可继续追加到 H2 白名单

### 4.4 H3：疑似 HR
满足以下条件时判为 `H3`：

1. 已匹配到花名册
2. 不满足 H1
3. 不满足 H2
4. `组织路径名称` 包含 `人力`、`人事` 或 `HR`

说明：
- 这类人员通常挂在 HR 部门、人力共享、人事远程交付或人力行政服务组织下
- 但目前证据不足，不能直接判 H1，也未进入 H2 白名单
- 该类人群保留为“待补充规则”的疑似 HR 池

当前统计下，H3 共 `115` 人。

### 4.5 HX：不是 HR
满足以下条件时判为 `HX`：

- 已匹配到花名册
- 不满足 H1
- 不满足 H2
- 不满足 H3

当前统计下，HX 共 `151,164` 人。

## 5. 二级职能的使用建议

### 5.1 二级职能在本方案中的定位
`二级职能名称` 建议用于两类输出：

1. 作为 H1 / H2 人员的 HR 子域标签
2. 作为审核解释信息输出给规则引擎或日志

不建议在当前版本单独使用：
- `二级职能名称` 单独命中某关键词
- 就直接把申请人从 HX 提升到 H1 或 H2

原因：
- 当前真实数据中，二级职能没有单独新增出额外 HR 人员
- 它更适合做“解释”，而不是扩人群

### 5.2 建议的 HR 子域标签
对已判定为 `H1` 或 `H2` 的人员，建议进一步输出 `hr_subdomain`：

- `人力资源` -> `hr_general`
- `人事运营` -> `hr_operations`
- `招聘` / `招聘外包服务` -> `recruiting`
- `薪酬绩效` -> `compensation_performance`
- `员工关系` -> `employee_relations`
- `人才发展` / `组织发展` -> `org_talent_development`
- `人力业务支持` -> `hr_business_support`
- 其他 -> `other_hr_domain`

## 6. 建议输出字段
建议在后续规则输入对象中，为申请人增加以下衍生字段：

- `roster_match_status`
  - `MATCHED / UNMATCHED`
- `hr_type`
  - `H1 / H2 / H3 / HX`
- `is_hr_staff`
  - 当 `hr_type in ('H1', 'H2')` 时为 `true`
- `is_suspected_hr_staff`
  - 当 `hr_type = 'H3'` 时为 `true`
- `hr_primary_evidence`
  - 如 `level1_function_name`、`position_name`、`standard_position_name`、`org_path_name`
- `hr_primary_value`
  - 命中的原始值
- `hr_subdomain`
  - HR 子域标签
- `hr_judgement_reason`
  - 便于审计追溯，例如：
    - `level1_is_hr`
    - `position_keyword_hit`
    - `standard_position_keyword_hit`
    - `weak_signal_position_promoted_to_h2`
    - `org_path_keyword_hit_only`
    - `roster_not_found`

## 7. SQL 实现建议

### 7.1 当前落地说明
从方案命名上，后续应对接：
- `申请单基本信息`

但当前数据库中实际物理表名仍为：
- `basic_info`

在完成正式迁移前，可先临时用 `basic_info` 验证 SQL；迁移完成后再切到 `申请单基本信息`。

### 7.2 建议 SQL
```sql
WITH applicant AS (
    SELECT
        document_no,
        BTRIM(employee_no) AS employee_no
    FROM "申请单基本信息"
),
roster AS (
    SELECT
        BTRIM(employee_no) AS employee_no,
        employee_name,
        level1_function_name,
        level2_function_name,
        position_name,
        standard_position_name,
        org_path_name
    FROM "在职花名册表"
),
joined AS (
    SELECT
        a.document_no,
        a.employee_no AS applicant_employee_no,
        r.employee_name,
        r.level1_function_name,
        r.level2_function_name,
        r.position_name,
        r.standard_position_name,
        r.org_path_name,
        CASE
            WHEN r.employee_no IS NULL THEN 'UNMATCHED'
            ELSE 'MATCHED'
        END AS roster_match_status,
        CASE
            WHEN r.employee_no IS NULL THEN NULL
            WHEN COALESCE(r.level1_function_name, '') = '人力资源' THEN 'H1'
            WHEN COALESCE(r.position_name, '') ~ '(人力|人事|HRBP|HR共享|业务HR|项目HR|综合人事|人力资源|人力行政|人力业务支持|hrbp|hr)'
              THEN 'H1'
            WHEN COALESCE(r.standard_position_name, '') ~ '(人力|人事|HRBP|HR共享|综合人事|人力资源|人力行政|人力业务支持|人力综合|hrbp|hr)'
              THEN 'H1'
            WHEN COALESCE(r.org_path_name, '') ~ '(人力|人事|HR|hr)'
             AND COALESCE(r.position_name, '') IN ('运营经理', '运营主管', '数据分析')
              THEN 'H2'
            WHEN COALESCE(r.org_path_name, '') ~ '(人力|人事|HR|hr)'
              THEN 'H3'
            ELSE 'HX'
        END AS hr_type,
        CASE
            WHEN r.employee_no IS NULL THEN 'roster_not_found'
            WHEN COALESCE(r.level1_function_name, '') = '人力资源' THEN 'level1_is_hr'
            WHEN COALESCE(r.position_name, '') ~ '(人力|人事|HRBP|HR共享|业务HR|项目HR|综合人事|人力资源|人力行政|人力业务支持|hrbp|hr)'
              THEN 'position_keyword_hit'
            WHEN COALESCE(r.standard_position_name, '') ~ '(人力|人事|HRBP|HR共享|综合人事|人力资源|人力行政|人力业务支持|人力综合|hrbp|hr)'
              THEN 'standard_position_keyword_hit'
            WHEN COALESCE(r.org_path_name, '') ~ '(人力|人事|HR|hr)'
             AND COALESCE(r.position_name, '') IN ('运营经理', '运营主管', '数据分析')
              THEN 'weak_signal_position_promoted_to_h2'
            WHEN COALESCE(r.org_path_name, '') ~ '(人力|人事|HR|hr)'
              THEN 'org_path_keyword_hit_only'
            ELSE 'no_hr_signal'
        END AS hr_judgement_reason,
        CASE
            WHEN COALESCE(r.level2_function_name, '') = '人力资源' THEN 'hr_general'
            WHEN COALESCE(r.level2_function_name, '') = '人事运营' THEN 'hr_operations'
            WHEN COALESCE(r.level2_function_name, '') IN ('招聘', '招聘外包服务') THEN 'recruiting'
            WHEN COALESCE(r.level2_function_name, '') = '薪酬绩效' THEN 'compensation_performance'
            WHEN COALESCE(r.level2_function_name, '') = '员工关系' THEN 'employee_relations'
            WHEN COALESCE(r.level2_function_name, '') IN ('人才发展', '组织发展') THEN 'org_talent_development'
            WHEN COALESCE(r.level2_function_name, '') = '人力业务支持' THEN 'hr_business_support'
            ELSE NULL
        END AS hr_subdomain
    FROM applicant a
    LEFT JOIN roster r
        ON a.employee_no = r.employee_no
)
SELECT *
FROM joined;
```

## 8. 风险与边界

### 8.1 当前申请单样本不足
当前申请单主表仅 `1` 条，且未匹配到花名册，因此：
- 现阶段无法用申请单样本充分回归验证
- 方案结论主要建立在全量花名册统计基础上

### 8.2 H2 是白名单提升规则
当前 H2 不是自然强信号，而是：
- 从弱信号人群中专项调查
- 再人工确认提升

因此 H2 应保持“小而稳”的白名单特征，不建议一次性扩得过宽。

### 8.3 H3 需要继续补充规则
当前 H3 只是“疑似 HR 池”，后续可以继续补充：
- 新的弱信号职位白名单
- 更细的组织路径规则
- 特定人力共享中心、HRBP 组、组织发展组等增强规则

### 8.4 组织路径不能直接替代职位判断
路径中含 `人力` / `人事` 的人员，不一定是 HR，本次已看到以下非 HR 样本：
- 行政
- 法务
- 司机
- PMO
- 运营
- 廉正监察

因此凡是“只靠组织路径命中”的人员，至少应先落到 H2 或 H3，而不能直接提升为 H1。

## 9. 验收标准
满足以下条件可视为方案完成：

- 可按申请人工号关联到 `在职花名册表`
- 能输出 `H1 / H2 / H3 / HX`
- 能额外输出 `roster_match_status`
- `一级职能名称 = 人力资源` 的人员可稳定识别为 `H1`
- `职位名称` / `标准岗位名称` 明确出现 `人力 / 人事 / HRBP / HR共享` 等文本的人员可识别为 `H1`
- 弱信号中 `职位名称 in ('运营经理', '运营主管', '数据分析')` 且路径命中 HR 关键词的人员可识别为 `H2`
- 仅因 `组织路径名称` 含 `人力 / 人事 / HR` 的其他弱信号人员识别为 `H3`
- 其他已匹配人员识别为 `HX`

## 10. 交付物
- 方案文档：`方案计划文档/010申请单申请人HR与疑似HR识别方案文档.md`
