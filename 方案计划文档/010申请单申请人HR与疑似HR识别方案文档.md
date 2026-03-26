# 方案编号010：申请单申请人HR与疑似HR识别方案文档

## 1. 方案目标
基于最新 `在职花名册表` 全量快照，结合以下字段及外部组织属性口径生成 `人员属性查询`，并在申请单侧通过 `申请单基本信息.工号 -> 人员属性查询.工号` 关联判断申请人属于哪一类 HR 身份：

- `一级职能名称`
- `二级职能名称`
- `职位名称`
- `标准岗位名称`
- `组织路径名称`
- `组织属性查询.万御城市营业部`
- `组织列表.责任HR工号`

本方案目标：
- 建立一套可执行的 `H1 / H2 / H3 / HY / HX` 分类口径
- 将“明确 HR”“推定 HR”“责任 HR”“疑似 HR”“不是 HR”分层处理
- 避免把挂在人力组织下的行政、法务、司机、PMO、运营等岗位直接误判为 HR
- 为后续规则引擎输出稳定、可解释、可扩展的申请人身份标签

本方案明确采用“**职位**”，不采用“职务”字段作为判定主依据。

## 2. 分类定义

### 2.1 最终分类
本方案建议将申请人 HR 判断分为 5 类：

- `H1`
  - 可以直接判断为 HR
  - 即当前已有明确信号规则可直接命中
- `H2`
  - 推定为 HR
  - 即当前在弱信号样本中，经调查后可单独提升为 HR 的职位
- `H3`
  - 责任 HR
  - 即当前未命中 `H1 / H2`，但命中 `组织列表` 责任 HR 集合
  - 用于标识“组织配置上的责任 HR”，不等同于严格的 HR 职能身份
- `HY`
  - 疑似 HR
  - 当前存在 HR 弱信号，但证据不足，待后续继续补充规则
- `HX`
  - 不是 HR

### 2.2 未匹配花名册的处理
`H1 / H2 / H3 / HY / HX` 建议仅用于**成功匹配花名册**的申请人。

若申请人工号未匹配到 `在职花名册表`，建议：
- `roster_match_status = UNMATCHED`
- `hr_type = NULL`

不建议把“未匹配花名册”直接归为 `HX`，原因如下：
- 未匹配不等于不是 HR
- 可能是花名册快照缺失、工号口径差异、历史人员或数据同步延迟
- 即使该工号命中 `组织列表` 的责任 HR 集合，也建议先保留 `UNMATCHED`，避免把“组织配置角色”误当作“在职 HR 身份”

如业务侧强制要求必须给出单一分类编码，可临时记为：
- `hr_type = HX`
- 同时保留 `hr_judgement_reason = roster_not_found`

## 3. 数据基础与实际分析结果

### 3.1 本次分析数据
本次分析基于本地 PostgreSQL 中的真实花名册数据：
- 花名册表：`在职花名册表`
- 数据量：`154,849` 人
- 花名册快照日期：`2026-03-11`

责任 HR 集合来源于本地 PostgreSQL 中的最新组织列表批次：
- 组织列表表：`组织列表`
- 最新批次：`orglist_20260313_121148`
- 责任 HR 去重人数：`586`
- 其中可匹配到当前花名册：`578`
- 未匹配到当前花名册：`8`

同时核对了当前申请单主表现状：
- 当前数据库中的申请单主表为 `申请单基本信息`
- 当前仅有 `1` 条申请单主表记录
- 该记录的 `工号` 未匹配到当前花名册

因此，本方案的判定口径主要依据**全量花名册分布分析**得出，而不是依据当前申请单样本。

### 3.2 关键字段完整度
`在职花名册表` 中与本方案相关字段的可用情况如下：

- `一级职能名称`：`152,492`
- `二级职能名称`：`152,492`
- `职位名称`：`154,849`
- `标准岗位名称`：`152,492`
- `组织路径名称`：`154,849`
- `department_id`：`154,849`

与 `组织属性查询` 的关联情况如下：
- 关联键：`在职花名册表.department_id = 组织属性查询.org_code`
- 可关联到 `组织属性查询` 的人数：`154,849`
- 其中 `wanyu_city_sales_department` 非空人数：`34,256`

与 `组织列表` 的关联情况如下：
- 责任 HR 识别键：`在职花名册表.人员编号 = 组织列表.责任HR工号`
- 建议使用 `组织列表` 最新 `import_batch_no` 提取责任 HR 集合
- 当前最新批次去重后责任 HR 共 `586` 人，其中 `578` 人能匹配到当前花名册

结论：
- `一级职能名称`、`二级职能名称`、`标准岗位名称` 完整度较高，可作为主要判定字段
- `职位名称`、`组织路径名称` 基本全量可用
- `department_id -> 组织属性查询.org_code` 的关联链路可直接落地，可支撑基于 `wanyu_city_sales_department` 的增强判断
- `组织列表.责任HR工号` 可作为 `H3` 的责任 HR 判定来源
- `职务` 字段本次不纳入主判定逻辑

### 3.3 H1 强信号分析
基于真实数据统计，得到以下事实：

- `一级职能名称 = 人力资源`：`3,492` 人
- `职位名称` 命中 `人力 / 人事 / HR / HRBP` 等显式关键词：`2,334` 人
- `标准岗位名称` 命中 `人力 / 人事 / HR / HRBP` 等显式关键词：`2,723` 人
- `职位名称` 包含 `组织发展 / 薪酬 / 绩效 / 福利`：按最终口径纳入 `H1` 的共 `7` 人
  - 其中 `目标与绩效管理专业总监` 仅在 `组织路径名称` 命中 `HR 组织路径` 时才纳入 H1
- `组织属性查询.wanyu_city_sales_department` 非空，且 `职位名称 in ('认证中心负责人', '服务站总站长')`：`32` 人
  - `服务站总站长`：`16` 人，原本已因 `一级职能名称 = 人力资源` 进入 H1
  - `认证中心负责人`：`16` 人，属于该条规则额外覆盖的人群
- 本次新增 `组织发展中心 / 组织人才中心` 组织口径后，`H1` 总量不变
  - 新增组织口径主要用于扩展 `HR 组织路径` 的识别范围，影响 `H2 / H3 / HY`
  - 不将 `组织发展中心 / 组织人才中心` 直接单独视为 `H1` 强信号

说明：
- 以上为各强信号字段的命中量统计，字段之间存在交叉重叠，不能直接相加
- 最终 `H1` 人数以 `4.2` 规则优先级判定结果为准

按当前 H1 口径：
- `一级职能名称 = 人力资源`
- 或 `职位名称` 明确命中 HR 关键词
- 或 `职位名称` 包含 `组织发展 / 薪酬 / 绩效 / 福利`
  - 其中 `目标与绩效管理专业总监` 需同时满足 `组织路径名称` 命中 HR 组织路径口径
- 或 `标准岗位名称` 明确命中 HR 关键词
- 或 `wanyu_city_sales_department` 非空，且 `职位名称 in ('认证中心负责人', '服务站总站长')`

则可识别出 `H1` 共 `3,588` 人。

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
- 因此 `二级职能名称` 适合作为解释字段，不建议在当前版本单独作为 H1 / H2 / HY 的主判定条件

### 3.5 弱信号分析
本方案将以下路径统一视为 `HR 组织路径`：

- `人力`
- `人事`
- `组织发展中心`
- `组织人才中心`

若仅使用 `HR 组织路径` 作为判定条件，会命中一批弱信号人员。

在去除 H1 强信号后，这批弱信号人员共 `128` 人，其中：
- `H2`：`61` 人
- `H3`：`2` 人
- `HY`：`65` 人

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
- 新增 `组织发展中心 / 组织人才中心` 口径后，额外进入弱信号池的人员共 `14` 人
  - 其中 `2` 人提升为 `H2`
  - `12` 人进入 `HY`
- 当前版本新增 `组织单位 = 人力资源与行政服务中心` 且 `职位名称` 包含 `员工体验与行政` 的专项提升规则，额外有 `48` 人从弱信号池提升为 `H2`
- 在当前版本中，若弱信号人员同时属于 `责任 HR`，且命中 H2 提升规则，则优先进入 `H2`；其余责任 HR 继续优先进入 `H3`，不再落入 `HY`

补充调查结论：
- 当前花名册中，`组织路径名称` 包含 `HR` 的记录仅 `12` 人，对应 `3` 条唯一路径
- 其中只有 `1` 条路径不含 `人力 / 人事`：`万物云_祥盈企服_公共服务中心_深圳片区_深圳公共服务中心_A万科集团HR-SSC`
- 该路径下 `2` 名人员本身已因其他强信号进入 `H1`
- 因此将组织路径规则从“`人力 / 人事 / HR`”收窄为“`人力 / 人事`”仍然成立
- 但业务补充确认：`组织发展中心 / 组织人才中心` 也应视为 HR 组织路径的一部分

### 3.6 H3 责任 HR 分析
在当前规则下，`H3` 定义为：

- 已匹配到花名册
- 不满足 `H1`
- 不满足 `H2`
- 但命中 `组织列表` 最新批次中的责任 HR 集合

按当前数据统计：
- `H3` 共 `81` 人
- 这 `81` 人共覆盖 `6,317` 个组织
- 在最新责任 HR 集合 `586` 人中，分类分布为：
  - `H1`：`491`
  - `H2`：`6`
  - `H3`：`81`
  - `UNMATCHED`：`8`

`H3` 的典型职位包括：
- `运营管理中心经理`
- `运营支持部负责人`
- `业务支持部负责人`
- `综合管理`
- `廉正监察专家`

说明：
- `H3` 是“责任配置角色”口径，不是“严格 HR 职能身份”口径
- 因此 `H3` 适合用于识别“组织上承担责任 HR 职责的人”，但不建议与 `H1 / H2` 混为同一强度的人力职能口径

## 4. H1 / H2 / H3 / HY / HX 判定口径

### 4.1 第一步：按工号匹配花名册
建议使用：
- `申请单基本信息.工号`
- 关联 `人员属性查询.工号`

匹配口径建议：
- 两侧都做 `BTRIM`
- 保持文本型，不转数值，避免前导零丢失

若未匹配到花名册，则：
- `roster_match_status = UNMATCHED`
- `hr_type = NULL`
- `hr_judgement_reason = roster_not_found`

补充定义：
- 本方案中的 `HR 组织路径` 指 `组织路径名称` 命中以下任一文本：
  - `人力`
  - `人事`
  - `组织发展中心`
  - `组织人才中心`
- 本方案中的 `责任 HR 集合` 指 `组织列表` 最新批次中去重后的 `责任HR工号`

规则优先级建议为：
- `H1 -> H2 -> H3 -> HY -> HX`

在进入上述分类前，先执行职位排除规则：
- 若 `职位名称 = 残疾人`
- 或 `职位名称` 包含 `采集人`
- 则直接从 HR 口径中剔除，按 `HX` 处理
- 该排除规则优先级高于 `H1 / H2 / H3 / HY`

### 4.2 H1：可以直接判断为 HR
满足任一条件即可判为 `H1`：

1. `一级职能名称 = 人力资源`
2. `职位名称` 明确命中 HR 关键词
3. `职位名称` 包含 `组织发展`、`薪酬`、`绩效`、`福利`
   - 其中 `目标与绩效管理专业总监` 仅在 `组织路径名称` 命中 `HR 组织路径` 时纳入 `H1`
4. `标准岗位名称` 明确命中 HR 关键词
5. 通过 `department_id -> 组织属性查询.org_code` 关联后，`wanyu_city_sales_department` 非空，且 `职位名称 in ('认证中心负责人', '服务站总站长')`

H1 显式关键词口径采用保守规则，优先识别以下显式文本：
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

其中：
- `出纳兼人事`、`行政人事主管`、`人力行政主管` 等也会因 `职位名称` 命中显式 HR 关键词进入 `H1`
- 若后续业务希望将“行政人事 / 人力行政”类岗位下调到 `HY` 或 `HX`，需另行收紧 `H1` 的显式关键词规则

这样设计的原因：
- 可直接识别 `HRBP`、`人事运营`、`人力资源岗`、`人力综合管理`、`人事远程交付中心总经理` 等明确 HR 身份
- 按当前规则，`职位` 包含 `组织发展 / 薪酬 / 绩效 / 福利` 时通常视为 H1；但 `目标与绩效管理专业总监` 必须同时位于 `HR 组织路径` 下才纳入 H1
- 可补充识别万御城市营业部体系下的 `认证中心负责人`
- `服务站总站长` 虽当前样本已被 `一级职能名称 = 人力资源` 覆盖，但保留在该规则中更稳，便于后续职能口径变化时仍可判定为 H1
- `组织发展中心 / 组织人才中心` 在当前版本中用于扩展 `HR 组织路径`，不单独直接提升为 `H1`
- 不会因为 `招聘`、`培训`、`人才发展` 等词出现在非 HR 职位里而误放大人群

### 4.3 H2：推定为 HR
`H2` 的定义是：
- 当前不满足 H1
- 但位于 HR 弱信号人群中
- 且经专项调查后，某些职位应从弱信号提升为“推定 HR”

当前版本先纳入以下 H2 提升条件：
- `组织单位 = 人力资源与行政服务中心`，且 `职位名称` 包含 `员工体验与行政`
- `运营经理`
- `运营主管`
- `数据分析`
- `组织与效能资深总监`
- `部门负责人`
- `AI与流程变革资深总监`
- `平台与运营资深总监`
- `总裁类 / 总经理类`
  - 即 `职位名称` 包含 `总裁` 或 `总经理`
  - 如：`副总裁`、`副总经理`、`助理总经理`、`组织人才中心总经理`

并且必须同时满足：
1. 不满足 H1
2. 满足以下任一条件：
   - `组织单位 = 人力资源与行政服务中心`，且 `职位名称` 包含 `员工体验与行政`
   - `组织路径名称` 命中 `HR 组织路径`，且 `职位名称` 属于上述 H2 白名单

当前调查结果中，H2 共 `61` 人，样本包括：
- `员工体验与行政` / `员工体验与行政专业经理` / `员工体验与行政高级专业经理` / `员工体验与行政资深专业经理`
  - 位于 `人力资源与行政服务中心` 的人员共 `48` 人
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
- `组织与效能资深总监`
  - `万物云_万物云本部_人力资源与行政服务中心_BG人力资源行政服务中心_组织与效能组`
- `部门负责人`
  - `万物云_祥盈企服_远程交付中心_财务远程交付中心_武汉财务远程交付中心_人力资源组`
- `AI与流程变革资深总监`
  - `万物云_万物云本部_人力资源与行政服务中心_BG人力资源行政服务中心_平台与运营组`
- `平台与运营资深总监`
  - `万物云_万物云本部_人力资源与行政服务中心_BG人力资源行政服务中心_平台与运营组`
- `副总裁`
  - `万物云_投资与创新发展中心_万物成长被投企业_重庆天骄_组织发展中心`
- `组织人才中心总经理`
  - `万物云_万物梁行_万物梁行本部_组织人才中心`
- `总经理（三类）` / `副总经理`
  - `万物云_投资与创新发展中心_万物成长被投企业_重庆天骄_西南区域_成都分公司_人力行政部`

说明：
- H2 是“经人工调查后提升”的职位型规则
- 当前 H2 由“职位白名单”与“组织范围限定的专项岗位”共同组成
- `总裁 / 总经理` 类职位只在其所在组织命中 `HR 组织路径` 时进入 `H2`
- `员工体验与行政` 相关岗位仅在 `组织单位 = 人力资源与行政服务中心` 时进入 `H2`
- `总裁 / 总经理` 类职位进入 `H2` 后，其 `hr_subdomain` 统一归入 `hr_management`
- 后续若发现更多应提升岗位，可继续追加到 H2 白名单

### 4.4 H3：责任 HR
满足以下条件时判为 `H3`：

1. 已匹配到花名册
2. 不满足 H1
3. 不满足 H2
4. `工号` 命中 `组织列表` 最新批次责任 HR 集合

说明：
- `H3` 代表“责任配置角色上的 HR”
- `H3` 不要求其 `职位名称`、`标准岗位名称`、`一级职能名称` 命中 HR 强信号
- `H3` 可覆盖运营、综合、监察等职位，只要其在组织配置中被维护为责任 HR
- 当前统计下，`H3` 共 `81` 人

### 4.5 HY：疑似 HR
满足以下条件时判为 `HY`：

1. 已匹配到花名册
2. 不满足 H1
3. 不满足 H2
4. 不满足 H3
5. `组织路径名称` 命中 `HR 组织路径`

说明：
- 这类人员通常挂在 HR 部门、人力共享、人事远程交付或人力行政服务组织下
- 当前也包含挂在 `组织发展中心 / 组织人才中心` 下、但尚未命中 `H2` 白名单的人员
- 但目前证据不足，不能直接判 H1，也未进入 H2 白名单
- 若该人员同时属于 `责任 HR`，则优先落入 `H3`，不再停留在 `HY`
- 该类人群保留为“待补充规则”的疑似 HR 池

按当前口径统计，HY 当前共 `65` 人，其中包含新增纳入 `组织发展中心 / 组织人才中心` 弱信号池、但未命中 `H2 / H3` 的人员。

### 4.6 HX：不是 HR
满足以下条件时判为 `HX`：

- 已匹配到花名册
- 且命中职位排除规则
- 或不满足 H1
- 不满足 H2
- 不满足 H3
- 不满足 HY

当前统计下，HX 共 `151,054` 人。

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

- 映射顺序建议为：先按专项组织路径 / 岗位规则命中新增中文子域；若未命中，再按历史 `职位名称 / 二级职能名称 / 一级职能名称` 规则回落
- `组织路径名称` 以 `万物云_祥盈企服_公共服务中心` 开头 -> `企服属地公服`
- `组织路径名称` 以 `万物云_祥盈企服_远程交付中心_人事远程交付中心_BP` 开头 -> `企服远程外服`
- `组织路径名称` 以 `万物云_祥盈企服_远程交付中心_人事远程交付中心` 开头，且不属于 `_BP` 分支 -> `企服人事远程交付中心`
- `标准岗位名称 = HRBP` -> `HRBP`
- `组织路径名称` 以 `万物云_万物云本部_人力资源与行政服务中心` 开头，且包含 `人事交付服务组` -> `属地服务站`
- `组织路径名称` 以 `万物云_万物云本部_人力资源与行政服务中心` 开头，且不包含 `BG人力资源行政服务中心` -> `战区人行`
- `二级职能名称` / `职位名称` / `标准岗位名称` 包含 `招聘` -> `招聘岗位`
- 若以上新增规则均未命中，则按历史 fallback 规则继续映射
- `职位名称` 包含 `总裁` / `总经理` -> `hr_management`
- `人力资源` -> `hr_general`
- `人事运营` -> `hr_operations`
- `招聘` / `招聘外包服务` -> `recruiting`
- `薪酬绩效` -> `compensation_performance`
- `员工关系` -> `employee_relations`
- `人才发展` / `组织发展` -> `org_talent_development`
- `人力业务支持` -> `hr_business_support`
- `一级职能名称 in ('管理', '职能综合管理')` -> `hr_management`
- 其他 -> `other_hr_domain`

对 `H3` 人员：
- 建议保留 `hr_subdomain = NULL`
- 因为 `H3` 来源于 `责任 HR` 组织配置，不等价于 HR 职能子域

## 6. 建议输出字段
建议在后续规则输入对象中，为申请人增加以下衍生字段：

- `roster_match_status`
  - `MATCHED / UNMATCHED`
- `hr_type`
  - `H1 / H2 / H3 / HY / HX`
- `is_responsible_hr`
  - 当申请人工号命中 `组织列表` 最新责任 HR 集合时为 `true`
- `is_hr_staff`
  - 若业务需要“宽口径 HR”，当 `hr_type in ('H1', 'H2', 'H3')` 时为 `true`
  - 若业务需要“严格职能 HR”，建议仅将 `H1 / H2` 视为 `true`
- `is_suspected_hr_staff`
  - 当 `hr_type = 'HY'` 时为 `true`
- `hr_primary_evidence`
  - 如 `level1_function_name`、`position_name`、`standard_position_name`、`org_path_name`、`wanyu_city_sales_department`
- `hr_primary_value`
  - 命中的原始值
- `hr_subdomain`
  - 当 `hr_type in ('H1', 'H2')` 时输出 HR 子域标签
  - 若属于 `H1 / H2` 但未命中已定义子域，则输出 `other_hr_domain`
  - 若 `hr_type = 'H3'`，则建议为空
  - 若 `hr_type in ('HY', 'HX')` 或 `roster_match_status = UNMATCHED`，则建议为空
- `hr_judgement_reason`
  - 便于审计追溯，例如：
    - `level1_is_hr`
    - `position_keyword_hit`
    - `position_org_dev_comp_perf_benefit_hit`
    - `standard_position_keyword_hit`
    - `wanyu_city_sales_department_position_hit`
    - `weak_signal_management_position_promoted_to_h2`
    - `weak_signal_position_promoted_to_h2`
    - `org_unit_employee_experience_position_promoted_to_h2`
    - `responsible_hr_hit`
    - `org_path_keyword_hit_only`
    - `position_excluded_from_hr`
    - `roster_not_found`

### 6.1 当前落库物理表与字段
按 `AGENTS.md` 中文物理字段规范，本方案派生结果不再耦合在 `申请单基本信息` 中，而是单独落到 `人员属性查询`。

表职责与粒度：
- `申请单基本信息`
  - 仍只承载权限申请单主表字段
  - 保留 `单据编号`、`工号`、`权限对象`、`申请理由`、`单据状态`、`人事管理组织`、`公司`、`部门`、`职位`、`申请日期`、`最新审批时间`、`采集次数` 等字段
- `人员属性查询`
  - 以最新 `在职花名册表` 为基础全量刷新
  - 物理粒度为“人员粒度”
  - 主键建议为 `工号`
  - 申请单申请人使用 `申请单基本信息.工号` 关联本表获取 HR 类型及来源属性

`人员属性查询` 建议至少落以下中文字段，逻辑口径与上文英文字段一一对应：

| 逻辑字段 | 物理字段 |
| --- | --- |
| `employee_no` | `工号` |
| `employee_name` | `姓名` |
| `department_id` | `部门ID` |
| `org_unit_name` | `组织单位` |
| `employee_group` | `员工组` |
| `employee_subgroup` | `员工子组` |
| `level1_function_name` | `一级职能名称` |
| `level2_function_name` | `二级职能名称` |
| `position_name` | `职位名称` |
| `standard_position_name` | `标准岗位名称` |
| `org_path_name` | `组织路径名称` |
| `wanyu_city_sales_department` | `万御城市营业部` |
| `responsible_hr_employee_no` | `责任HR工号` |
| `responsible_hr_import_batch_no` | `责任HR导入批次号` |
| `roster_query_date` | `花名册查询日期` |
| `roster_import_batch_no` | `花名册导入批次号` |
| `roster_match_status` | `花名册匹配状态` |
| `hr_type` | `申请人HR类型` |
| `is_responsible_hr` | `是否责任HR` |
| `is_hr_staff` | `是否HR人员` |
| `is_suspected_hr_staff` | `是否疑似HR人员` |
| `hr_primary_evidence` | `HR主判定依据` |
| `hr_primary_value` | `HR主判定值` |
| `hr_subdomain` | `HR子域` |
| `hr_judgement_reason` | `HR判定原因` |
| `created_at` | `记录创建时间` |
| `updated_at` | `记录更新时间` |

说明：
- 物理表字段使用中文
- 逻辑编码值仍保留本方案中定义的稳定枚举值与原因码
- 若后续规则引擎或查询层需要英文逻辑名，可在查询层或对象映射层转换，不新增英文业务物理列

## 7. SQL 实现建议

### 7.1 当前落地说明
当前数据库中：
- `申请单基本信息` 仅保留权限申请主表字段，不再承载 HR 判定结果
- `人员属性查询` 由 `在职花名册表` 更新完成后同步全量刷新
- `组织列表` 需已有最新批次数据，用于提取 `责任 HR 集合`

因此 `7.2` 的示例 SQL 应基于 `在职花名册表 + 组织属性查询 + 组织列表` 生成 `人员属性查询`；申请单使用时再按 `申请单基本信息.工号 -> 人员属性查询.工号` 关联。

说明：
- 当前库中物理字段已中文化
- 因此 `7.2` 采用“中文物理字段 + 英文逻辑别名”写法，既可直接执行，也便于表达规则逻辑
- 当申请人工号无法关联到 `人员属性查询` 时，查询层或规则层应视为 `roster_match_status = UNMATCHED`

### 7.2 建议 SQL
```sql
TRUNCATE TABLE "人员属性查询";

WITH roster AS (
    SELECT
        BTRIM("人员编号") AS employee_no,
        BTRIM("部门ID") AS department_id,
        "查询日期" AS roster_query_date,
        "导入批次号" AS roster_import_batch_no,
        "姓名" AS employee_name,
        "员工组" AS employee_group,
        "员工子组" AS employee_subgroup,
        "一级职能名称" AS level1_function_name,
        "二级职能名称" AS level2_function_name,
        "职位名称" AS position_name,
        "标准岗位名称" AS standard_position_name,
        "组织路径名称" AS org_path_name
    FROM "在职花名册表"
),
org_attr AS (
    SELECT
        BTRIM("行政组织编码") AS org_code,
        "组织单位" AS org_unit_name,
        "万御城市营业部" AS wanyu_city_sales_department
    FROM "组织属性查询"
),
latest_batch AS (
    SELECT "导入批次号"
    FROM "组织列表"
    ORDER BY "记录创建时间" DESC
    LIMIT 1
),
responsible_hr AS (
    SELECT DISTINCT
        BTRIM("责任HR工号") AS employee_no
    FROM "组织列表"
    WHERE "导入批次号" = (SELECT "导入批次号" FROM latest_batch)
      AND NULLIF(BTRIM("责任HR工号"), '') IS NOT NULL
),
base_joined AS (
    SELECT
        r.employee_no,
        r.employee_name,
        r.department_id,
        o.org_unit_name,
        r.employee_group,
        r.employee_subgroup,
        r.roster_query_date,
        r.roster_import_batch_no,
        r.level1_function_name,
        r.level2_function_name,
        r.position_name,
        r.standard_position_name,
        r.org_path_name,
        o.org_unit_name,
        o.wanyu_city_sales_department,
        rh.employee_no AS responsible_hr_employee_no,
        (SELECT "导入批次号" FROM latest_batch) AS responsible_hr_import_batch_no,
        CASE
            WHEN rh.employee_no IS NOT NULL THEN TRUE
            ELSE FALSE
        END AS is_responsible_hr,
        CASE
            WHEN COALESCE(r.org_path_name, '') LIKE '%人力%'
              OR COALESCE(r.org_path_name, '') LIKE '%人事%'
              OR COALESCE(r.org_path_name, '') LIKE '%组织发展中心%'
              OR COALESCE(r.org_path_name, '') LIKE '%组织人才中心%'
              THEN TRUE
            ELSE FALSE
        END AS is_hr_org_path,
        CASE
            WHEN r.employee_no IS NULL THEN 'UNMATCHED'
            ELSE 'MATCHED'
        END AS roster_match_status
    FROM roster r
    LEFT JOIN org_attr o
        ON r.department_id = o.org_code
    LEFT JOIN responsible_hr rh
        ON r.employee_no = rh.employee_no
),
classified AS (
    SELECT
        b.*,
        CASE
            WHEN b.employee_name IS NULL THEN NULL
            WHEN COALESCE(b.level1_function_name, '') = '人力资源' THEN 'H1'
            WHEN COALESCE(b.position_name, '') ~ '(人力|人事|HRBP|HR共享|业务HR|项目HR|综合人事|人力资源|人力行政|人力业务支持|hrbp|hr)'
              THEN 'H1'
            WHEN COALESCE(b.position_name, '') = '目标与绩效管理专业总监'
             AND b.is_hr_org_path
              THEN 'H1'
            WHEN COALESCE(b.position_name, '') <> '目标与绩效管理专业总监'
             AND COALESCE(b.position_name, '') ~ '(组织发展|薪酬|绩效|福利)'
              THEN 'H1'
            WHEN COALESCE(b.standard_position_name, '') ~ '(人力|人事|HRBP|HR共享|综合人事|人力资源|人力行政|人力业务支持|人力综合|hrbp|hr)'
              THEN 'H1'
            WHEN COALESCE(b.wanyu_city_sales_department, '') <> ''
             AND COALESCE(b.position_name, '') IN ('认证中心负责人', '服务站总站长')
              THEN 'H1'
            WHEN b.is_hr_org_path
             AND (
                    COALESCE(b.position_name, '') IN ('组织与效能资深总监', '部门负责人', 'AI与流程变革资深总监', '平台与运营资深总监')
                    OR COALESCE(b.position_name, '') ~ '(总裁|总经理)'
                 )
              THEN 'H2'
            WHEN b.is_hr_org_path
             AND COALESCE(b.position_name, '') IN ('运营经理', '运营主管', '数据分析')
              THEN 'H2'
            WHEN COALESCE(b.org_unit_name, '') = '人力资源与行政服务中心'
             AND COALESCE(b.position_name, '') LIKE '%员工体验与行政%'
              THEN 'H2'
            WHEN COALESCE(b.is_responsible_hr, FALSE)
              THEN 'H3'
            WHEN b.is_hr_org_path
              THEN 'HY'
            ELSE 'HX'
        END AS hr_type,
        CASE
            WHEN b.employee_name IS NULL THEN NULL
            WHEN COALESCE(b.level1_function_name, '') = '人力资源' THEN 'level1_function_name'
            WHEN COALESCE(b.position_name, '') ~ '(人力|人事|HRBP|HR共享|业务HR|项目HR|综合人事|人力资源|人力行政|人力业务支持|hrbp|hr)'
              THEN 'position_name'
            WHEN COALESCE(b.position_name, '') = '目标与绩效管理专业总监'
             AND b.is_hr_org_path
              THEN 'position_name'
            WHEN COALESCE(b.position_name, '') <> '目标与绩效管理专业总监'
             AND COALESCE(b.position_name, '') ~ '(组织发展|薪酬|绩效|福利)'
              THEN 'position_name'
            WHEN COALESCE(b.standard_position_name, '') ~ '(人力|人事|HRBP|HR共享|综合人事|人力资源|人力行政|人力业务支持|人力综合|hrbp|hr)'
              THEN 'standard_position_name'
            WHEN COALESCE(b.wanyu_city_sales_department, '') <> ''
             AND COALESCE(b.position_name, '') IN ('认证中心负责人', '服务站总站长')
              THEN 'wanyu_city_sales_department'
            WHEN b.is_hr_org_path
             AND (
                    COALESCE(b.position_name, '') IN ('组织与效能资深总监', '部门负责人', 'AI与流程变革资深总监', '平台与运营资深总监')
                    OR COALESCE(b.position_name, '') ~ '(总裁|总经理)'
                 )
              THEN 'position_name'
            WHEN b.is_hr_org_path
             AND COALESCE(b.position_name, '') IN ('运营经理', '运营主管', '数据分析')
              THEN 'position_name'
            WHEN COALESCE(b.org_unit_name, '') = '人力资源与行政服务中心'
             AND COALESCE(b.position_name, '') LIKE '%员工体验与行政%'
              THEN 'org_unit_name+position_name'
            WHEN COALESCE(b.is_responsible_hr, FALSE)
              THEN 'responsible_hr_employee_no'
            WHEN b.is_hr_org_path
              THEN 'org_path_name'
            ELSE NULL
        END AS hr_primary_evidence,
        CASE
            WHEN b.employee_name IS NULL THEN NULL
            WHEN COALESCE(b.level1_function_name, '') = '人力资源' THEN b.level1_function_name
            WHEN COALESCE(b.position_name, '') ~ '(人力|人事|HRBP|HR共享|业务HR|项目HR|综合人事|人力资源|人力行政|人力业务支持|hrbp|hr)'
              THEN b.position_name
            WHEN COALESCE(b.position_name, '') = '目标与绩效管理专业总监'
             AND b.is_hr_org_path
              THEN b.position_name
            WHEN COALESCE(b.position_name, '') <> '目标与绩效管理专业总监'
             AND COALESCE(b.position_name, '') ~ '(组织发展|薪酬|绩效|福利)'
              THEN b.position_name
            WHEN COALESCE(b.standard_position_name, '') ~ '(人力|人事|HRBP|HR共享|综合人事|人力资源|人力行政|人力业务支持|人力综合|hrbp|hr)'
              THEN b.standard_position_name
            WHEN COALESCE(b.wanyu_city_sales_department, '') <> ''
             AND COALESCE(b.position_name, '') IN ('认证中心负责人', '服务站总站长')
              THEN b.wanyu_city_sales_department
            WHEN b.is_hr_org_path
             AND (
                    COALESCE(b.position_name, '') IN ('组织与效能资深总监', '部门负责人', 'AI与流程变革资深总监', '平台与运营资深总监')
                    OR COALESCE(b.position_name, '') ~ '(总裁|总经理)'
                 )
              THEN b.position_name
            WHEN b.is_hr_org_path
             AND COALESCE(b.position_name, '') IN ('运营经理', '运营主管', '数据分析')
              THEN b.position_name
            WHEN COALESCE(b.org_unit_name, '') = '人力资源与行政服务中心'
             AND COALESCE(b.position_name, '') LIKE '%员工体验与行政%'
              THEN COALESCE(b.org_unit_name, '') || '|' || COALESCE(b.position_name, '')
            WHEN COALESCE(b.is_responsible_hr, FALSE)
              THEN b.employee_no
            WHEN b.is_hr_org_path
              THEN b.org_path_name
            ELSE NULL
        END AS hr_primary_value,
        CASE
            WHEN b.employee_name IS NULL THEN 'roster_not_found'
            WHEN COALESCE(b.level1_function_name, '') = '人力资源' THEN 'level1_is_hr'
            WHEN COALESCE(b.position_name, '') ~ '(人力|人事|HRBP|HR共享|业务HR|项目HR|综合人事|人力资源|人力行政|人力业务支持|hrbp|hr)'
              THEN 'position_keyword_hit'
            WHEN COALESCE(b.position_name, '') = '目标与绩效管理专业总监'
             AND b.is_hr_org_path
              THEN 'position_org_dev_comp_perf_benefit_hit'
            WHEN COALESCE(b.position_name, '') <> '目标与绩效管理专业总监'
             AND COALESCE(b.position_name, '') ~ '(组织发展|薪酬|绩效|福利)'
              THEN 'position_org_dev_comp_perf_benefit_hit'
            WHEN COALESCE(b.standard_position_name, '') ~ '(人力|人事|HRBP|HR共享|综合人事|人力资源|人力行政|人力业务支持|人力综合|hrbp|hr)'
              THEN 'standard_position_keyword_hit'
            WHEN COALESCE(b.wanyu_city_sales_department, '') <> ''
             AND COALESCE(b.position_name, '') IN ('认证中心负责人', '服务站总站长')
              THEN 'wanyu_city_sales_department_position_hit'
            WHEN b.is_hr_org_path
             AND (
                    COALESCE(b.position_name, '') IN ('组织与效能资深总监', '部门负责人', 'AI与流程变革资深总监', '平台与运营资深总监')
                    OR COALESCE(b.position_name, '') ~ '(总裁|总经理)'
                 )
              THEN 'weak_signal_management_position_promoted_to_h2'
            WHEN b.is_hr_org_path
             AND COALESCE(b.position_name, '') IN ('运营经理', '运营主管', '数据分析')
              THEN 'weak_signal_position_promoted_to_h2'
            WHEN COALESCE(b.org_unit_name, '') = '人力资源与行政服务中心'
             AND COALESCE(b.position_name, '') LIKE '%员工体验与行政%'
              THEN 'org_unit_employee_experience_position_promoted_to_h2'
            WHEN COALESCE(b.is_responsible_hr, FALSE)
              THEN 'responsible_hr_hit'
            WHEN b.is_hr_org_path
              THEN 'org_path_keyword_hit_only'
            ELSE 'no_hr_signal'
        END AS hr_judgement_reason
    FROM base_joined b
),
joined AS (
    SELECT
        c.*,
        CASE
            WHEN c.hr_type NOT IN ('H1', 'H2') THEN NULL
            WHEN COALESCE(c.org_path_name, '') LIKE '万物云_祥盈企服_公共服务中心%' THEN '企服属地公服'
            WHEN COALESCE(c.org_path_name, '') LIKE '万物云_祥盈企服_远程交付中心_人事远程交付中心_BP%' THEN '企服远程外服'
            WHEN COALESCE(c.org_path_name, '') LIKE '万物云_祥盈企服_远程交付中心_人事远程交付中心%' THEN '企服人事远程交付中心'
            WHEN COALESCE(c.standard_position_name, '') = 'HRBP' THEN 'HRBP'
            WHEN COALESCE(c.org_path_name, '') LIKE '万物云_万物云本部_人力资源与行政服务中心%'
             AND COALESCE(c.org_path_name, '') LIKE '%人事交付服务组%'
              THEN '属地服务站'
            WHEN COALESCE(c.org_path_name, '') LIKE '万物云_万物云本部_人力资源与行政服务中心%'
             AND COALESCE(c.org_path_name, '') NOT LIKE '%BG人力资源行政服务中心%'
              THEN '战区人行'
            WHEN COALESCE(c.level2_function_name, '') LIKE '%招聘%'
              OR COALESCE(c.position_name, '') LIKE '%招聘%'
              OR COALESCE(c.standard_position_name, '') LIKE '%招聘%'
              THEN '招聘岗位'
            WHEN COALESCE(c.position_name, '') ~ '(总裁|总经理)' THEN 'hr_management'
            WHEN COALESCE(c.level2_function_name, '') = '人力资源' THEN 'hr_general'
            WHEN COALESCE(c.level2_function_name, '') = '人事运营' THEN 'hr_operations'
            WHEN COALESCE(c.level2_function_name, '') IN ('招聘', '招聘外包服务') THEN 'recruiting'
            WHEN COALESCE(c.level2_function_name, '') = '薪酬绩效' THEN 'compensation_performance'
            WHEN COALESCE(c.level2_function_name, '') = '员工关系' THEN 'employee_relations'
            WHEN COALESCE(c.level2_function_name, '') IN ('人才发展', '组织发展') THEN 'org_talent_development'
            WHEN COALESCE(c.level2_function_name, '') = '人力业务支持' THEN 'hr_business_support'
            WHEN COALESCE(c.level1_function_name, '') IN ('管理', '职能综合管理') THEN 'hr_management'
            ELSE 'other_hr_domain'
        END AS hr_subdomain
    FROM classified c
)
INSERT INTO "人员属性查询" (
    "工号",
    "姓名",
    "部门ID",
    "组织单位",
    "员工组",
    "员工子组",
    "一级职能名称",
    "二级职能名称",
    "职位名称",
    "标准岗位名称",
    "组织路径名称",
    "万御城市营业部",
    "责任HR工号",
    "责任HR导入批次号",
    "花名册查询日期",
    "花名册导入批次号",
    "花名册匹配状态",
    "申请人HR类型",
    "是否责任HR",
    "是否HR人员",
    "是否疑似HR人员",
    "HR主判定依据",
    "HR主判定值",
    "HR子域",
    "HR判定原因",
    "记录创建时间",
    "记录更新时间"
)
SELECT
    employee_no,
    employee_name,
    department_id,
    org_unit_name,
    employee_group,
    employee_subgroup,
    level1_function_name,
    level2_function_name,
    position_name,
    standard_position_name,
    org_path_name,
    wanyu_city_sales_department,
    responsible_hr_employee_no,
    responsible_hr_import_batch_no,
    roster_query_date,
    roster_import_batch_no,
    roster_match_status,
    hr_type,
    is_responsible_hr,
    (hr_type IN ('H1', 'H2', 'H3')) AS is_hr_staff,
    (hr_type = 'HY') AS is_suspected_hr_staff,
    hr_primary_evidence,
    hr_primary_value,
    hr_subdomain,
    hr_judgement_reason,
    NOW(),
    NOW()
FROM joined;
```

## 8. 风险与边界

### 8.1 当前申请单样本不足
当前申请单主表仅 `1` 条，且未匹配到花名册，因此：
- 现阶段无法用申请单样本充分回归验证
- 方案结论主要建立在全量花名册统计基础上

### 8.2 H2 是白名单 / 范围提升规则
当前 H2 不是自然强信号，而是：
- 从弱信号人群中专项调查
- 再人工确认提升
- 部分岗位需要叠加明确组织范围才进入 H2

因此 H2 应保持“小而稳”的可解释特征，不建议一次性扩得过宽。

### 8.3 H1 的绩效类职位需要保留组织约束
当前规则中：
- `职位名称` 包含 `组织发展 / 薪酬 / 绩效 / 福利` 的岗位通常进入 H1
- 但 `目标与绩效管理专业总监` 需同时满足 `组织路径名称` 命中 `HR 组织路径`

这样做的原因是：`目标与绩效管理专业总监` 这类职位名称虽然含有 `绩效`，但实际可能挂在非 HR 组织中。

当前已观察到的样本包括：
- `目标与绩效管理专业总监`
  - `万物云_万科物业_财务及运营管理部`
  - 因组织并非 `HR 组织路径`，当前不再纳入 `H1`
- `绩效经理`
  - `万物云_投资与创新发展中心_万物成长被投企业_重庆天骄_组织发展中心`

这说明：
- 不能仅因职位中含 `绩效` 就直接判为 HR
- 对 `目标与绩效管理专业总监` 需要额外叠加组织约束

### 8.4 HY 需要继续补充规则
当前 HY 只是“疑似 HR 池”，后续可以继续补充：
- 新的弱信号职位白名单
- 更细的组织路径规则
- 特定人力共享中心、HRBP 组、组织发展组等增强规则

### 8.5 H3 是责任配置口径，不是严格职能口径
`H3` 的来源是 `组织列表.责任HR工号`，反映的是：
- 某人被维护为组织的 `责任 HR`

但这不必然等价于：
- 该人本身的 `一级职能 / 二级职能 / 职位 / 标准岗位` 属于 HR

当前 `H3` 样本中已可见：
- 运营
- 综合
- 监察
- 业务支持

因此：
- 若业务要看“严格 HR 身份”，建议仍以 `H1 / H2` 为主
- 若业务要看“系统中被配置为责任 HR 的人”，则建议纳入 `H3`

### 8.6 组织路径不能直接替代职位判断
路径命中 `HR 组织路径` 的人员，不一定是 HR，本次已看到以下非 HR 样本：
- 行政
- 法务
- 司机
- PMO
- 运营
- 廉正监察

因此凡是“只靠组织路径命中”的人员，至少应先落到 H2 或 HY，而不能直接提升为 H1。

## 9. 验收标准
满足以下条件可视为方案完成：

- 花名册导入完成后可同步全量刷新 `人员属性查询`
- `申请单基本信息` 不新增、不写入 HR 判定字段
- 可按申请人工号关联到 `人员属性查询`
- 可按申请人工号关联到 `组织列表` 最新责任 HR 集合
- 能输出 `H1 / H2 / H3 / HY / HX`
- 能额外输出 `roster_match_status`
- 能额外输出 `is_responsible_hr`
- `一级职能名称 = 人力资源` 的人员可稳定识别为 `H1`
- `职位名称` / `标准岗位名称` 明确出现 `人力 / 人事 / HRBP / HR共享` 等文本的人员可识别为 `H1`
- `职位名称` 包含 `组织发展 / 薪酬 / 绩效 / 福利` 的人员可识别为 `H1`
  - 但 `目标与绩效管理专业总监` 必须同时满足 `组织路径名称` 命中 `HR 组织路径`
- `department_id` 可关联到 `组织属性查询.org_code`，且 `wanyu_city_sales_department` 非空并且 `职位名称 in ('认证中心负责人', '服务站总站长')` 的人员可识别为 `H1`
- `组织路径名称` 命中 `HR 组织路径（人力 / 人事 / 组织发展中心 / 组织人才中心）`，且 `职位名称` 属于 `组织与效能资深总监 / 部门负责人 / AI与流程变革资深总监 / 平台与运营资深总监 / 总裁类 / 总经理类` 的人员可识别为 `H2`
- 弱信号中 `职位名称 in ('运营经理', '运营主管', '数据分析')` 且路径命中 `HR 组织路径` 的人员可识别为 `H2`
- `department_id` 可关联到 `组织属性查询.org_code`，且 `组织单位 = 人力资源与行政服务中心` 并且 `职位名称` 包含 `员工体验与行政` 的人员可识别为 `H2`
- 未命中 `H1 / H2`，但命中 `组织列表` 最新责任 HR 集合的人员可识别为 `H3`
- 仅因 `组织路径名称` 命中 `HR 组织路径`、且未命中 `H3` 的其他弱信号人员识别为 `HY`
- 其他已匹配人员识别为 `HX`

## 10. 交付物
- 方案文档：`方案计划文档/010申请单申请人HR与疑似HR识别方案文档.md`
- 发布与回滚步骤：`方案计划文档/010A人员属性查询发布与回滚步骤.md`
 - 建表与升级：`automation/sql/001_permission_apply_collect.sql`、`automation/sql/019_person_attributes.sql`、`automation/sql/021_drop_applicant_hr_columns_from_basic_info.sql`
- 验收 SQL：`automation/sql/020_person_attributes_acceptance.sql`
- 写库实现：`automation/db/postgres.py`
