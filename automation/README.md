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

## 3. Commands
Health check:
```bash
python automation/scripts/run.py check --headed
```

Login and save auth state:
```bash
python automation/scripts/run.py login --headed
python automation/scripts/run.py login --config automation/config/settings.prod.yaml --credentials automation/config/credentials.prod.local.yaml --headed
```

Permission collection:
```bash
python automation/scripts/run.py collect --limit 3 --dry-run --headed
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

## 4. Output
- logs: `automation/logs/`
- screenshots: `automation/screenshots/`
- state: `automation/state/`
- downloads: `automation/downloads/`
- SQL: `automation/sql/001_permission_apply_collect.sql`
- SQL: `automation/sql/002_active_roster.sql`

## 5. Notes
- Prod roster flow targets `https://hr.onewo.com/ierp/?formId=home_page`.
- The actual recent-menu entry is `在职人员花名册`.
- The actual export dialog button is `转后台执行`.
- Report scheme and employment type are both selected through F7 dialogs.
- The roster import writes into PostgreSQL table `在职花名册表`.
