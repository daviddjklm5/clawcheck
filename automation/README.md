# iERP Automation (Plan 001)

Python + Playwright automation skeleton for:
- `https://thr.onewo.com:8443/ierp/?formId=home_page`

## 1. Setup

```bash
cd automation
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

## 2. Configure

```bash
cp config/settings.example.yaml config/settings.yaml
cp config/selectors.example.yaml config/selectors.yaml
```

Edit:
- `config/settings.yaml`: account, runtime path, browser options
- `config/settings.yaml -> db`: PostgreSQL connection used by `collect`
- `config/selectors.yaml`: real selectors from your iERP page
- `config/credentials.local.yaml`: local account/password file (git ignored)
- Optional secure override: export `IERP_USERNAME` and `IERP_PASSWORD` (highest priority)
- Optional DB override: export `IERP_PG_HOST`, `IERP_PG_PORT`, `IERP_PG_DBNAME`, `IERP_PG_USER`, `IERP_PG_PASSWORD`, `IERP_PG_SCHEMA`, `IERP_PG_SSLMODE`

## 3. Commands

```bash
# connectivity + page readiness check
python scripts/run.py check

# login once and save auth state
python scripts/run.py login

# run example business flow
python scripts/run.py run

# collect permission applications and dump JSON only
python scripts/run.py collect --dry-run --document-no QX-260311-00000223 --headless

# collect permission applications and write PostgreSQL
python scripts/run.py collect --document-no QX-260311-00000223 --headless

# enable create/save flow
python scripts/run.py run --create --reason "自动化测试申请"

# explicitly enable submit (high-risk operation)
python scripts/run.py run --create --submit
```

Use local credentials file:

```bash
# edit this file first
vim config/credentials.local.yaml
python scripts/run.py login
```

Use env credentials (override local file):

```bash
export IERP_USERNAME='your_real_user'
export IERP_PASSWORD='your_real_password'
python scripts/run.py login
```

If credentials are still placeholders, `login` will prompt for username/password interactively.

Optional args:

```bash
python scripts/run.py run --headed
python scripts/run.py collect --limit 3 --dry-run --headless
python scripts/run.py run --config config/settings.yaml --selectors config/selectors.yaml
python scripts/run.py run --credentials config/credentials.local.yaml
```

Record selectors:

```bash
bash scripts/codegen.sh
python scripts/probe.py --headless
```

## 4. Output
- logs: `automation/logs/`
- screenshots: `automation/screenshots/`
- state: `automation/state/auth.json`
- PostgreSQL schema SQL: `automation/sql/001_permission_apply_collect.sql`

## 5. Notes
- For self-signed HTTPS certs, `ignore_https_errors: true` is enabled by default.
- CAPTCHA is not auto-solved. Keep `require_manual_captcha: true` and complete it manually when prompted.
- Replace placeholder selectors before using `run` for real submission.
- `run` is navigation-only by default (no create/save).
- `--create` enables create/save; `--submit` must be explicitly added for submission.
- `collect` reads permission-application todo records, dumps JSON locally, and writes PG unless `--dry-run` is set.
