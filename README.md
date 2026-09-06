# SkillSwap

SkillSwap is a Flask/MySQL community platform for finding verified local mentors, managing learning relationships, tracking progress, chatting, reviewing completed learning, and buying skill-related products.

## Features

- Learner, Mentor, and Admin roles with approval workflow
- Password hashing, session authentication, CSRF protection, and role authorization
- Dynamic skill and location-based mentor discovery
- Private verification documents and validated profile/product uploads
- Learning requests, one-to-one chat with polling, notifications, plans, progress, and completion
- Server-calculated demo payments, commissions, mentor earnings, subscriptions, premium plans, and revenue ledger
- Store catalogue, cart, stock control, demo checkout, and order history
- Learner reviews, mentor ratings, and admin moderation
- Responsive Bootstrap UI with SkillSwap blue/orange branding

## Technology and architecture

Python, Flask, Flask-SQLAlchemy, MySQL/PyMySQL, Jinja templates, HTML5, CSS3, JavaScript, and Bootstrap. The application is organized into `models/`, `routes/`, `services/`, `templates/`, `static/`, and `database/`. No Node.js frontend is required.

## Project structure

```text
app.py                 Flask factory, CLI commands, error handlers
config.py              Environment-driven configuration
models/                Normalized SQLAlchemy models
routes/                Public, auth, role, store, learning, payment, review, and admin routes
services/              Payments, revenue, premium, uploads, notifications, security
templates/             Jinja pages and role-specific screens
static/                CSS, JavaScript, logo, public assets
private_uploads/       Protected verification documents (never public)
database/              MySQL bootstrap SQL
Dockerfile             Flask container
docker-compose.yml     Flask + MySQL services
```

## Local setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
Copy-Item .env.example .env
pip install -r requirements.txt
flask --app app init-db
flask --app app seed-admin
flask --app app run --debug
```

Set `ADMIN_EMAIL` and an `ADMIN_PASSWORD` of at least 12 characters in `.env` before running `seed-admin`. Use `flask --app app check-db` to verify the configured MySQL connection. Existing data is preserved by `init-db`/`upgrade-db`; these commands use `create_all` plus additive compatibility columns.

## Docker

```powershell
Copy-Item .env.example .env
docker compose up --build
```

The app is available at `http://localhost:5000`. MySQL credentials are supplied through `.env` and are not hardcoded in the application.

Docker runs in development mode with the project folder live-mounted into the container. After the first build, edits to Python, HTML templates, CSS, or JavaScript are reflected automatically (refresh the browser; Flask reloads after Python changes). Rebuild only after changing `requirements.txt` or the `Dockerfile`:

```powershell
docker compose up --build
```

## Demo payments

Payments currently use a **Demo Payment Provider and do not process real money**. Checkout pages explicitly state that no real money will be collected. The provider records successful and failed demo outcomes, references, commissions, mentor earnings, subscriptions, orders, and revenue records so a real gateway can be integrated later without changing route-level business logic.

## Testing

```powershell
python -m compileall -q app.py models routes services
python -m pip check
docker compose config --quiet
```

The automated test setup uses `create_app('testing')` with an isolated SQLite database when a local MySQL daemon is unavailable. Production/development configuration remains MySQL-backed through `DATABASE_URL` or the `MYSQL_*` variables.

## Security and privacy

Never commit `.env`, private uploads, or user data. Passwords are hashed; private identity/certificate files are stored outside `static/` and served only to authorized admins. Uploads use safe generated filenames, extension/MIME validation, and a configurable size limit. Set a strong `SECRET_KEY` and use `SESSION_COOKIE_SECURE=1` behind HTTPS.

## Known limitations and future improvements

- The payment provider is intentionally a demo implementation; a production gateway still needs credentials and webhook verification.
- Chat uses secure polling rather than a WebSocket service.
- Mapping and distance calculations are not required for the MVP and can be added with a credential-free/open provider later.
- A migration framework such as Alembic can replace the additive upgrade helper as the schema evolves.

## Demonstration flow

1. Seed and log in as Admin; approve learner and mentor applications.
2. Log in as Learner; update interests, search by skill/location, request a mentor, and chat.
3. Log in as Mentor; accept the request, create a plan, and update progress to 100%.
4. Return as Learner; run the clearly labeled demo payment, review the completed mentor, use the store, and activate a premium plan.
5. Return as Admin; show user filters, verification documents, skills, payments, reviews, premium plans, and the revenue dashboard.
