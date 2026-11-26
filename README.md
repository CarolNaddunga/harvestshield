# HARVESTSHIELD

Working local agricultural cooperative portal for fictional GreenFields Produce Cooperative. CSC3117, Carol. Synthetic records and fictional UGX amounts only; no payments or external services.

## What works now

- Sign-in/out for farmer, clerk and administrator roles.
- Create account form for new farmers with a linked profile and immediate sign-in.
- Farmers view only their own profile, delivery records and fictional amounts/statuses.
- Clerks register validated deliveries; crop prices and pending status are enforced by the server.
- Administrators approve/reject deliveries and view the integrity trail and account directory.
- Searchable delivery lists, database-backed dashboards and timestamped audit events.
- The approved photographic overview, local images and licences.

Not implemented: staff account provisioning, password changes, role editing or quantity/price edits to existing deliveries. The account directory is read-only. This is a working core portal, not the completed exam portfolio or a public production system.

## Public hosting on Render

Use the root `render.yaml` Blueprint to create the free web service and free PostgreSQL database together. Enter two distinct passwords of at least 16 characters when Render prompts for `HARVESTSHIELD_ADMIN_PASSWORD` and `HARVESTSHIELD_CLERK_PASSWORD`. They remain in Render environment settings, outside GitHub. The database expires after 30 days; no paid resources are requested. Wait for the service to report Live and use the HTTPS URL Render assigns.

## Windows PowerShell: Docker Desktop

Transfer and extract the latest ZIP. Put its `harvestshield-app` folder inside `Documents\Carol_HARVESTSHIELD_CSC3117`. Open Docker Desktop with its Linux engine running.

```powershell
Set-Location "$HOME\Documents\Carol_HARVESTSHIELD_CSC3117\harvestshield-app"
docker compose build
docker compose run --rm --no-deps portal python -m scripts.seed
docker compose up -d
Start-Process "http://127.0.0.1:8080/login"
Invoke-RestMethod "http://127.0.0.1:8080/health"
```

Seed prompts for a local demo password (12+ characters); do not reuse a real password. Accounts: `farmer01` through `farmer10`, `clerk01`, `clerk02`, `admin`. All synthetic fixture accounts use that chosen password. No default password is shipped in the source/image. If updating an existing populated database, seed preserves its data and password. New session/rate-limit tables are created automatically on startup.

Initial seed: 10 farmers, 2 clerks, 1 admin, 18 deliveries, 2,610 kg, 6 pending, UGX 8,829,000 approved. Totals change as you perform actions. `/health` reports status `ok` and phase `core-portal`.

To apply an updated application to an existing Docker installation:

```powershell
docker compose up -d --build
docker compose logs portal
```

`docker compose down` stops containers while retaining the named database volume. `docker compose down --volumes` permanently deletes that demo database: preserve evidence before deliberately resetting it.

First build needs internet for packages/images. Runtime assets and database are local. The base image supports architecture selection including Linux ARM64. Docker configuration uses non-root UID, read-only root filesystem, dropped capabilities, an internal bridge and localhost-only published port. Compose syntax validates, but Docker image execution and Windows Snapdragon behaviour still require verification on the exam laptop. These development restrictions do not prove full host isolation or provide a malware sandbox.

## Local Python and tests

Python 3.11 or newer. From the project folder in PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m scripts.seed
.\.venv\Scripts\python.exe -m app.main
```

On macOS/Linux use `python3 -m venv .venv` and `.venv/bin/python` instead. The development server listens on 127.0.0.1:8080 by default; stop with Ctrl+C. Local HTTP is supported for this localhost demo. Public deployment requires additional HTTPS/deployment review and is not configured here.

## Try the actual workflow

1. Sign in as `clerk01`; select Record a delivery.
2. Choose Demo Farmer 01, maize, 150 kg, and a valid date. Submit.
3. Confirm UGX 180,000 and pending status. The clerk has no approval action.
4. Sign out and sign in as `farmer01`. Find and open the delivery.
5. Sign out and sign in as `farmer02`: that delivery must be absent; its direct URL is forbidden.
6. Sign in as `admin`, open the delivery, approve it, then view Integrity trail.
7. Confirm actor, record ID, timestamp and the pending → approved change.
8. Sign back in as `farmer01`; confirm approved status.

## Understand the files

- `app/main.py`: app creation, overview, static files, health and security response headers.
- `app/portal.py`: login, sessions, CSRF, permissions, role screens and transactional audit events.
- `app/database.py`: SQLite schema, synthetic seed, aggregates and connection transactions.
- `app/auth.py`: salted scrypt password hashes and constant-time verification.
- `app/models.py`: exact amount validation using Decimal, integer grams and UGX.
- `app/templates/home.html`, `app/static/style.css`: photo overview and responsive portal styles.
- `scripts/seed.py`: interactive demo-data initialization, never overwriting existing accounts.
- `tests/`: foundation and authenticated workflow verification.
- `docs/PHASE_2.md`: current security design, actual validation and remaining work.
- `CREDITS.md`: photo sources, authors, licence and transformations.
- `evidence/`: reserved for genuine lab evidence; no exam results are invented.

## Sources and assistance disclosure

Generated with OpenAI Codex assistance. Carol must inspect the source, run her own exam-lab tests and interpret actual observations. This is application development, not a completed examination submission. All photos are authentic, locally stored, credited and licensed as described in CREDITS.md; subjects are not labelled fictional GreenFields members.

References: https://docs.aiohttp.org/en/stable/web_reference.html , https://docs.python.org/3/library/sqlite3.html , https://docs.python.org/3/library/hashlib.html#hashlib.scrypt . aiohttp is pinned in requirements.txt for reproducibility. No intentional vulnerability is enabled. Recheck advisories before the later security-lab phase. The proposed exam CVE and instructor artifact remain separate future work.

## Create an account

Open `/login` and choose **Create an account**, or visit `/register`. Enter a synthetic display name, district, username, password and confirmation. Usernames use 3–32 letters/numbers/underscores and begin with a letter. Passwords use 12–128 characters. New registrations always receive the farmer role and see only their own initially empty records. Clerk/admin self-registration is not offered. Account and profile creation commit together, passwords are salted scrypt hashes, and registration is CSRF-protected and rate-limited. No email or outside service is required. Keep using synthetic information for this exam lab.

## Hosted Docker/Render variant

See `docs/RENDER_DEPLOYMENT.md`. The app now supports PostgreSQL via `DATABASE_URL` for persistent hosted data while preserving SQLite for the isolated local lab. Container startup reads Render's PORT, can enforce Secure cookies through `HARVESTSHIELD_SECURE_COOKIES=1`, and initialises a fresh hosted database with privately configured admin/clerk passwords. Hosted dependencies are pinned in `requirements-hosted.txt`; local SQLite installation still uses `requirements.txt`. No GitHub repository is required for the prebuilt Docker image route.
