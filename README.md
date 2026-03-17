# Tango Finance

A Django personal finance web application with multi-currency transaction tracking, AI-assisted entry, OTP-protected account operations, and admin-side risk monitoring.

**Live demo:** [tango-finance.replit.app](https://tango-finance.replit.app)

---

## Features

- **Authentication** — Email-based login, OTP-verified registration, OTP-protected password change and account deletion
- **Transactions** — Full CRUD with per-user ownership, pagination, search and date/type/category filtering
- **Multi-currency** — GBP, USD, CNY, EUR with automatic GBP normalization via exchange rate API
- **AI assistant (Nori)** — Groq-powered chat and agent endpoints for natural-language transaction entry
- **Categories** — Per-user custom categories with starter defaults on first login
- **Risk monitoring** — Heuristic + optional LLM-based risk scoring, surfaced in admin
- **Audit trail** — Automatic audit log on every transaction create/update/delete via Django signals
- **Cloudflare Turnstile** — Bot protection on registration and OTP flows
- **Admin panel** — User management, ban/unban, transaction search, audit logs, risk alerts

---

## Architecture

```
django_finances/       # Project config (settings, URLs, error handlers, middleware)
finance/
  views.py             # Web views: dashboard, profile, OTP flows, auth
  api_views.py         # DRF REST endpoints (AI agent + chat)
  models.py            # Transaction, Category, AuditLog, RiskAlert
  services/
    transactions.py    # Transaction create/update business logic
    risk.py            # Heuristic + LLM risk scoring
  signals.py           # Post-save/delete hooks → audit log + risk evaluation
  navigation.py        # Site search items for AI navigation
  constants.py         # Non-secret domain constants
  templates/           # Django HTML templates
  static/              # CSS, JS assets
user/
  models.py            # Custom email-based User model + EmailOTP
finance/management/commands/
  ensure_admin.py      # Auto-creates superuser on startup if missing
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.12 |
| Framework | Django 6.0.1 + Django REST Framework |
| Database | SQLite (local) / PostgreSQL (production) |
| Cache | Django cache framework (in-memory / Redis) |
| Server | Gunicorn + WhiteNoise |
| AI | Groq API (Llama 3) |
| Bot protection | Cloudflare Turnstile |

---

## Local Setup

```bash
git clone https://github.com/Hu-Tianze/Tango-Finance.git
cd Tango-Finance
pip install -r requirements.txt
```

Create a `.env` file in the project root (or export environment variables):

```env
DJANGO_SECRET_KEY=your-secret-key
DEBUG=True
```

Then run:

```bash
python manage.py migrate
python manage.py runserver
```

- App: `http://127.0.0.1:8000/finance/`
- Admin: `http://127.0.0.1:8000/admin/`

---

## Environment Variables

| Variable | Required | Purpose |
|---|---|---|
| `DJANGO_SECRET_KEY` | Yes | Django secret key |
| `DEBUG` | No (default `False`) | Enable debug mode |
| `APP_ENV` | No | Set to `local` for local development |
| `ALLOWED_HOSTS` | No | Comma-separated host allowlist |
| `CSRF_TRUSTED_ORIGINS` | No | Comma-separated trusted HTTPS origins |
| `DATABASE_URL` | No (local), Yes (production) | PostgreSQL connection string |
| `REDIS_URL` | No | Redis cache backend URL |
| `GROQ_API_KEY` | No | Enables AI chat and agent features |
| `CF_TURNSTILE_SITE_KEY` | No | Cloudflare Turnstile site key (frontend) |
| `CF_TURNSTILE_SECRET_KEY` | No | Cloudflare Turnstile secret (server validation) |
| `TURNSTILE_ENABLED` | No (default `False`) | Toggle Turnstile bot protection |
| `ENABLE_LLM_RISK` | No (default `False`) | Enable LLM-enhanced risk scoring |
| `DEFAULT_FROM_EMAIL` | No | Sender address for OTP emails |
| `EMAIL_HOST` / `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` | No | SMTP config for OTP delivery |
| `DJANGO_ADMIN_EMAIL` | No | Email for auto-created superuser on startup |
| `DJANGO_ADMIN_PASSWORD` | No | Password for auto-created superuser on startup |

---

## Replit Deployment

This repository is configured for one-click Replit deployment via `.replit` and `scripts/replit_start.sh`.

**Required secrets in Replit:**

| Secret | Value |
|---|---|
| `DJANGO_SECRET_KEY` | Any long random string |
| `ALLOWED_HOSTS` | `<your-replit-domain>,127.0.0.1,localhost` |
| `CSRF_TRUSTED_ORIGINS` | `https://<your-replit-domain>` |
| `DJANGO_ADMIN_EMAIL` | Admin account email |
| `DJANGO_ADMIN_PASSWORD` | Admin account password |

**Optional secrets:**

| Secret | Purpose |
|---|---|
| `GROQ_API_KEY` | AI assistant features |
| `CF_TURNSTILE_SITE_KEY` | Turnstile frontend widget |
| `CF_TURNSTILE_SECRET_KEY` | Turnstile server validation |
| `TURNSTILE_ENABLED` | Set `True` to activate Turnstile |
| `REDIS_URL` | Redis cache backend |

On startup, `scripts/replit_start.sh` will:
1. Apply database migrations
2. Run `ensure_admin` to auto-create the superuser if it doesn't exist
3. Start Gunicorn on `$PORT`

---

## Render Deployment

A `render.yaml` and `build.sh` are included for Render deployment.

1. Push to GitHub and connect the repo to Render via **New → Blueprint**
2. Render will create a web service and PostgreSQL database automatically
3. Set the required secrets listed above in the Render dashboard

---

## API Endpoints (Authenticated)

| Method | URL | Description |
|---|---|---|
| `POST` | `/finance/api/agent/transaction/` | AI agent: parse and record a transaction |
| `POST` | `/finance/api/chat/` | AI chat: conversational finance assistant |

---

## Security

- CSRF protection on all state-changing operations
- OTP codes stored as SHA-256 hashes, never in plaintext
- Rate limiting on OTP sends (60-second lockout)
- Cloudflare Turnstile on registration and OTP request flows
- `transaction.atomic()` on all critical write paths
- Soft-ban via `is_active=False` (data preserved, access revoked)
- Custom 400/403/404/500 error pages
- Admin paths bypass friendly redirect handlers

---

## Admin Panel

- **Users** — list, search, ban/unban
- **Transactions** — filterable/searchable full record view
- **Audit Logs** — read-only trace of all transaction events
- **Risk Alerts** — severity, score, status, detection source (heuristic / LLM / hybrid)

Staff users see an **Admin** link in the dashboard navigation bar.

---

## Tests

```bash
python manage.py check
python manage.py test
```

A GitHub Actions CI workflow runs on every push and pull request (`.github/workflows/ci.yml`).

---

## Known Limitations

- Email delivery requires SMTP configuration; no emails are sent in local development without it.
- Exchange rate API calls may fail without network access; hardcoded fallback rates are used.
- LLM risk scoring is off by default (`ENABLE_LLM_RISK=False`).
