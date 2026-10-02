# SkillSwap

SkillSwap is a Flask + MySQL platform that connects learners with mentors for skill-based learning. It includes mentor discovery, learning relationships, chat, progress tracking, payments/invoices, mentor earnings, withdrawals, reviews, a store, and an admin dashboard.

> **Note:** Payments and withdrawals are currently **demo/internal**. No real money is processed.

## Team Members
- Pratoy Barua
- Waled Rahman
- Asifur Rahman
- MD Rejwan

## Features

### Learner
- Sign up and accept Terms & Regulations.
- Search mentors by skill and location.
- View mentor profiles and request learning.
- Chat with mentors.
- View learning plans and progress.
- Receive and pay demo invoices.
- View payment/invoice history.
- Review and rate mentors.
- Unlock eligible mentor contact details through demo payment.
- Use the store and premium plans.
- Receive notifications.

### Mentor
- Sign up and submit verification information.
- Create and manage mentor profile and skills.
- Set skill pricing.
- Accept or reject learner requests.
- Manage active learners and learning plans.
- Update learning progress.
- Chat with learners.
- Issue one-time, weekly, or monthly payment requests.
- Track paid, pending, and overdue invoices.
- View earnings and available balance.
- Request withdrawals through bKash, Nagad, Rocket, Bank, or Card.
- View reviews and ratings.
- Sell products through the store.

### Admin
- Approve/reject learner and mentor accounts.
- Manage users, skills, reviews, and verification documents.
- Monitor mentor-learner relationships and progress.
- View payments and platform revenue.
- Manage mentor withdrawals.
- Manage premium plans and store products/orders.
- Monitor platform activity from the dashboard.

## Main Flow

```text
Sign Up
   ↓
Terms & Regulations
   ↓
Account Verification
   ↓
Learner ──→ Find Mentor ──→ Learning Request
                         ↓
                  Active Relationship
                         ↓
              Chat + Learning Progress
                         ↓
                  Invoices / Payments
                         ↓
              Completion + Review
```

## Payments & Earnings

The project supports:

- One-time payments
- Weekly billing
- Monthly billing
- Invoice generation
- Due dates and overdue status
- Mentor earnings calculation
- Platform commission
- Mentor withdrawal requests
- Withdrawal history and status management

Each recurring payment is issued as a separate invoice. Learners pay each invoice separately.

The current payment flow uses internal **demo payment references** and does not connect to real payment gateways.

## Mentor Profile Unlock

Learners can pay a configurable demo fee to unlock eligible professional contact information such as LinkedIn, GitHub, or a website.

## Store

The built-in store supports:

- Products and categories
- Cart and checkout
- Stock management
- Orders and order history
- Demo payments

## Chat, Reviews & Notifications

- One-to-one mentor-learner chat
- Learning progress updates
- 1–5 star mentor ratings
- Learner reviews
- Notifications for requests, payments, progress, reviews, and other account events

## AI Recommendation

The project includes an AI recommendation service for mentor matching. It contains distance calculation, experience scoring, search/recommendation logic, and an `/api/ai-recommend` endpoint.

## Security

- Password hashing
- Session-based authentication
- Role-based authorization
- CSRF protection
- Account approval and suspension controls
- Private verification document storage
- Upload validation
- Masked sensitive payment information

## Technology Stack

- **Backend:** Python, Flask, SQLAlchemy
- **Database:** MySQL 8.4
- **Frontend:** HTML, CSS, JavaScript, Jinja2, Bootstrap
- **Deployment:** Docker, Docker Compose

## Project Structure

```text
SkillSwap/
├── app.py
├── config.py
├── extensions.py
├── models/
├── routes/
├── services/
├── templates/
├── static/
├── database/
├── private_uploads/
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

## Run Locally

### Using Python

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
flask --app app init-db
flask --app app run --debug
```

Open:

```text
http://127.0.0.1:5000
```

### Using Docker

```powershell
docker compose up -d --build
```

Then open:

```text
http://127.0.0.1:5000
```

## Environment

Create `.env` from `.env.example` and configure the MySQL credentials, Flask secret key, and other required settings.

## Important Note

This project is intended as an academic/demo application. Payment, withdrawal, premium, and store transactions are implemented as application-level demo records and are not connected to real financial services.
