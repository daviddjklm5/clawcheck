# iERP Automation

## 1. Install
```bash
cd automation
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

## 2. Config
- UAT config: `automation/config/settings.yaml`
- Prod config: `automation/config/settings.prod.yaml`
- UAT credentials: `automation/config/credentials.local.yaml`
- Prod credentials: `automation/config/credentials.prod.local.yaml`
- Selectors: `automation/config/selectors.yaml`

Default runtime target:
- `check/login/run/collect/roster/orglist` use prod config by default when `--config` / `--credentials` are not passed.
- UAT remains available via explicit `--config automation/config/settings.yaml --credentials automation/config/credentials.local.yaml`.

## 3. Commands
Health check:
```bash
python automation/scripts/run.py check --headed
```

Login and save auth state:
```bash
python automation/scripts/run.py login --headed
python automation/scripts/run.py login --config automation/config/settings.yaml --credentials automation/config/credentials.local.yaml --headed
```

Permission collection:
```bash
python automation/scripts/run.py collect --limit 3 --dry-run --headed
```

Workflow run:
```bash
python automation/scripts/run.py run --headed
```

Active roster download + import:
```bash
python automation/scripts/run.py roster --headed
```

Recommended explicit prod command:
```bash
python automation/scripts/run.py roster \
  --config automation/config/settings.prod.yaml \
  --credentials automation/config/credentials.prod.local.yaml \
  --headed
```

Import an existing roster file only:
```bash
python automation/scripts/run.py roster \
  --config automation/config/settings.prod.yaml \
  --credentials automation/config/credentials.prod.local.yaml \
  --input-file automation/downloads/example.xlsx \
  --headless
```

Query only, without export/import:
```bash
python automation/scripts/run.py roster --skip-export --skip-import --headed
```

Organization list download + import:
```bash
python automation/scripts/run.py orglist --headed
```

Recommended explicit prod command:
```bash
python automation/scripts/run.py orglist   --config automation/config/settings.prod.yaml   --credentials automation/config/credentials.prod.local.yaml   --headed
```

Import an existing organization list file only:
```bash
python automation/scripts/run.py orglist   --config automation/config/settings.prod.yaml   --credentials automation/config/credentials.prod.local.yaml   --input-file automation/downloads/example_orglist.xlsx   --headless
```

Query only, without export/import:
```bash
python automation/scripts/run.py orglist --skip-export --skip-import --headed
```

Initialize permission catalog:
```bash
python automation/scripts/run.py rolecatalog \
  --config automation/config/settings.prod.yaml \
  --credentials automation/config/credentials.prod.local.yaml
```

## 4. Output
- logs: `automation/logs/`
- screenshots: `automation/screenshots/`
- state: `automation/state/`
- downloads: `automation/downloads/`
- SQL: `automation/sql/001_permission_apply_collect.sql`
- SQL: `automation/sql/002_active_roster.sql`
- SQL: `automation/sql/003_organization_list.sql`
- SQL: `automation/sql/004_city_warzone.sql`
- SQL: `automation/sql/005_organization_list_drop_extra_columns_json.sql`
- SQL: `automation/sql/007_organization_list_add_process_level_name.sql`
- SQL: `automation/sql/008_organization_list_standardize_latest_columns.sql`
- SQL: `automation/sql/009_permission_catalog.sql`
- SQL: `automation/sql/010_permission_apply_collect_migrate_basic_info.sql`

## 5. Notes
- Default home entry for `001/003/004` related browser actions is `https://hr.onewo.com/ierp/?formId=home_page`.
- Prod roster flow targets `https://hr.onewo.com/ierp/?formId=home_page`.
- The permission collect import auto-migrates legacy PostgreSQL table `basic_info` into `申请单基本信息` before writing.
- The actual recent-menu entry is `在职人员花名册`.
- The actual export dialog button is `转后台执行`.
- Report scheme and employment type are both selected through F7 dialogs.
- The roster import writes into PostgreSQL table `在职花名册表`.

- The orglist flow targets `组织快速维护 -> 万物云 -> 业务状态(已启用/已停用) -> 列表包含所有下级`.
- The actual orglist export path is `更多 -> 引出数据（按列表）`.
- The orglist import writes into PostgreSQL table `组织列表`.
- New source headers in the orglist workbook are auto-added as PostgreSQL physical columns (`TEXT`) instead of being kept in JSON.
- Verified in headed run on `2026-03-13`: the stable recent-menu entry is `li[data-menu-id-info*="217WYC/L9U7E"]`.
- Verified in headed run on `2026-03-13`: the `业务状态` compact filter uses `.kd-cq-querypanel-compact-item:has(.kd-cq-querypanel-compact-item-text[title="业务状态"])`.
- Verified in headed run on `2026-03-13`: selecting `已启用` + `已停用` changes the query result from `37` rows to `92` rows before enabling `列表包含所有下级`.
- Verified in headed run on `2026-03-13`: enabling `列表包含所有下级` after the dual-status filter expands the result to `96017` rows (`4801` pages).
- Verified in headed run on `2026-03-13`: export completes successfully and downloads `automation/downloads/20260313_115140_引出列表_组织快速维护_0313115015.xlsx`.
