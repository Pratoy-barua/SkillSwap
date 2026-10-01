# SkillSwap

SkillSwap is a Flask + MySQL community learning platform that connects learners with verified mentors based on skills and location. It supports mentor discovery, learning requests, mentor-learner relationships, learning plans and progress tracking, chat, reviews, invoicing, demo payments, mentor earnings and withdrawals, a product store, premium plans, notifications, and an admin management dashboard.

> **Important:** The payment system in this project is a **demo payment implementation**. It records payment outcomes and financial records inside the application but does not process real-world money.

---

## Table of Contents

- [Core Features](#core-features)
- [User Roles](#user-roles)
- [Main Application Flow](#main-application-flow)
- [Mentor Discovery](#mentor-discovery)
- [Learning & Mentorship](#learning--mentorship)
- [Payments & Invoicing](#payments--invoicing)
- [Mentor Earnings & Withdrawals](#mentor-earnings--withdrawals)
- [Reviews & Ratings](#reviews--ratings)
- [Mentor Profile Unlock](#mentor-profile-unlock)
- [Store](#store)
- [Premium Plans](#premium-plans)
- [Notifications & Chat](#notifications--chat)
- [Admin Dashboard](#admin-dashboard)
- [AI Recommendation System](#ai-recommendation-system)
- [Authentication & Security](#authentication--security)
- [Technology Stack](#technology-stack)
- [Project Structure](#project-structure)
- [Database](#database)
- [Installation](#installation)
- [Docker Setup](#docker-setup)
- [Useful Commands](#useful-commands)
- [Testing & Validation](#testing--validation)
- [Demo Flow](#demo-flow)
- [Configuration](#configuration)
- [Known Limitations](#known-limitations)
- [Future Improvements](#future-improvements)

---

## Core Features

### Learner

- Create a learner account after accepting the SkillSwap Terms & Regulations.
- Submit identity/verification information during registration.
- Maintain a learner profile and learning interests.
- Search mentors by skill and location.
- Use the skill search/autocomplete interface.
- View approved mentor profiles.
- Request to learn from a mentor.
- Cancel pending learning requests.
- View connected mentors.
- Chat with connected mentors.
- View learning plans and progress.
- Receive payment requests/invoices from mentors.
- Pay invoices through the demo payment flow.
- View payment history and invoice details.
- Review a mentor after the learning relationship is completed.
- Rate mentors from 1–5 stars.
- View mentor ratings/reviews published by other learners.
- Unlock available professional contact/profile details of eligible mentors through the demo payment flow.
- Use the SkillSwap store, cart, checkout, and order history.
- Activate available premium plans.
- Receive notifications for requests, payments, progress, reviews, chat, and other account events.

### Mentor

- Create a mentor account after accepting the SkillSwap Terms & Regulations.
- Submit verification documents for admin approval.
- Create and manage a mentor profile.
- Add skills they teach.
- Set skill pricing and pricing type.
- Specify experience and teaching type.
- Receive learner requests.
- Accept or reject learning requests.
- View active learners.
- Create learning plans.
- Define pricing, start date, and expected completion date for a learning plan.
- Update learner progress at 0%, 25%, 50%, 75%, or 100%.
- Add completed topics, current topic, remaining topics, and mentor notes.
- Chat with learners in active relationships.
- Create payment requests/invoices.
- Support one-time, weekly, and monthly billing records.
- Set payment due dates for invoices.
- Track paid, pending, and overdue payments.
- View earnings and invoice history.
- View available, pending, and withdrawn balances.
- Submit withdrawal requests using bKash, Nagad, Rocket, Bank Account, or Card options.
- View withdrawal details and withdrawal history.
- Receive learner reviews and ratings.
- View reviews from learners.
- Sell products through the SkillSwap store.
- Activate premium plans where available.

### Admin

- Dedicated admin login and role authorization.
- Approve or reject learner and mentor applications.
- Suspend or manage user accounts.
- View user details and verification documents.
- Manage skills and active/inactive skill status.
- Manage mentor profile unlock fee settings.
- Monitor learning relationships between mentors and learners.
- Open relationship details and monitor learning progress.
- View payment records and invoices.
- View platform revenue records.
- Manage mentor withdrawal requests.
- Process, complete, or reject withdrawals.
- Moderate learner reviews.
- Manage premium plans.
- Manage store categories, products, stock, and orders.
- View business and learning analytics from the admin dashboard.

---

## User Roles

SkillSwap has three primary roles:

| Role | Main Responsibility |
|---|---|
| **Learner** | Find mentors, learn, pay invoices, review mentors, and use the store |
| **Mentor** | Teach learners, manage learning progress, issue invoices, earn money, and request withdrawals |
| **Admin** | Verify users, manage the platform, moderate activity, process withdrawals, and monitor revenue |

New learner and mentor accounts are submitted for admin approval before normal platform access is granted.

---

## Main Application Flow

```text
Visitor
  │
  ├── Browse skills / mentors / store
  │
  └── Sign up
        │
        └── Terms & Regulations
              │
              ├── Learner registration
              └── Mentor registration
                    │
                    ▼
              Admin verification
                    │
          ┌─────────┴─────────┐
          ▼                   ▼
       Learner              Mentor
          │                   │
   Find a mentor       Add/manage skills
          │                   │
   Send learning request     │
          └─────────┬─────────┘
                    ▼
             Active Relationship
                    │
       ┌────────────┼────────────┐
       ▼            ▼            ▼
    Chat        Learning      Payments
                 Progress      /Invoices
                    │            │
                    ▼            ▼
                Completion   Mentor Earnings
                    │            │
                    ▼            ▼
                Review       Withdrawal
```

---

## Mentor Discovery

The public discovery system allows learners to find approved mentors using skill and location information.

Mentor search uses:

- Active skills
- Mentor experience
- Location/city/area
- Mentor teaching type
- Pricing information
- Mentor rating
- Profile availability

The home page includes a skill search interface. Existing skills can be matched while the user types, and the mentor search page provides the main discovery experience.

The application also contains an AI recommendation endpoint that produces mentor recommendations using the project's recommendation service.

---

## Learning & Mentorship

### Learning Requests

A learner can send a request to an approved mentor for a specific skill.

Mentors can:

- Accept the request
- Reject the request
- View pending requests
- View active learners

Once accepted, the platform creates an active learning relationship.

### Learning Relationship

A relationship connects:

- Learner
- Mentor
- Skill
- Learning request
- Conversation
- Learning plan
- Learning progress
- Payment/invoice records

The relationship also stores payment configuration such as:

- Payment type
- Payment frequency
- Payment amount
- Payment status

### Learning Plan

Mentors can create a plan containing:

- Title
- Description
- Pricing
- Pricing type
- Start date
- Expected completion date

### Learning Progress

Progress can be updated in fixed stages:

```text
0% → 25% → 50% → 75% → 100%
```

At 100%, the relationship is marked completed and the learner receives a completion notification.

---

## Payments & Invoicing

SkillSwap uses a demo payment provider for the current implementation.

### Demo Payment Provider

The provider generates internal demo references such as:

```text
DEMO-XXXXXXXX...
```

No external payment gateway is contacted.

### Payment Flow

Mentors can create payment requests for active learner relationships.

An invoice can contain:

- Invoice number
- Learner
- Mentor
- Skill
- Amount
- Payment type
- Frequency
- Billing period
- Description
- Due date
- Status
- Platform commission
- Mentor earning
- Payment date

### Billing Types

The current relationship/payment system supports:

- **One-time** payments
- **Weekly** recurring billing records
- **Monthly** recurring billing records

For recurring billing, mentors can create/update payment requests as new billing periods become due. Learners pay each issued invoice separately and receive an invoice/payment record for each payment.

### Payment Status

Common payment states include:

- Pending
- Paid
- Overdue
- Cancelled
- Successful/legacy successful records

The application automatically checks pending invoices against their due dates and can mark overdue invoices accordingly.

### Platform Commission

The platform commission is configurable through the `platform_commission_percent` setting. The current default in the payment service is **10%** when the setting has not yet been created.

For a payment:

```text
Gross Payment
      │
      ├── Platform Commission
      │
      └── Mentor Earning
```

---

## Mentor Earnings & Withdrawals

Mentors have a dedicated earnings/payment area.

The earnings system tracks:

- Total earnings
- Paid invoices
- Pending invoices
- Overdue invoices
- Active learner relationships
- Available balance
- Total withdrawn
- Pending withdrawals
- Withdrawal history

### Available Balance

The current service calculates withdrawable balance approximately as:

```text
Available Balance
= Total Paid Mentor Earnings
  - Completed Withdrawals
  - Pending/Processing Withdrawals
```

The balance cannot fall below zero.

### Withdrawal Methods

Supported withdrawal methods in the current model are:

- bKash
- Nagad
- Rocket
- Bank Account
- Card

Withdrawal requests have statuses such as:

- Pending
- Processing
- Completed
- Rejected
- Cancelled

The admin can process, complete, or reject withdrawal requests.

When a withdrawal is rejected, the amount can become available to the mentor again because only completed and currently reserved withdrawals are deducted from the available balance calculation.

Sensitive payment information is masked when displayed. The withdrawal model stores only limited card information such as the last four digits and does not store CVV.

---

## Reviews & Ratings

Learners can review mentors through the completed learning relationship.

A review contains:

- Learner
- Mentor
- Learning relationship
- Skill
- Rating
- Review text
- Status
- Created/updated timestamps

Ratings use a **1–5 star** scale.

The mentor rating is recalculated from published learner reviews.

Reviews can be:

- Published
- Moderated by Admin
- Deleted by the learner who created the review

Mentors can view their received reviews, and learners can see published feedback on mentor profiles/related views.

---

## Mentor Profile Unlock

SkillSwap contains a paid profile-detail unlock feature.

A learner can unlock professional contact/profile information for an eligible mentor through the demo payment flow.

The system currently checks that the mentor has at least one available professional contact field, such as:

- LinkedIn
- GitHub
- Website

If a mentor has no relevant professional contact details, the unlock option is not offered.

The unlock fee is configurable using the platform setting:

```text
mentor_profile_unlock_fee
```

The default service value is **৳50.00** if the setting does not exist.

The unlock payment is treated as platform revenue in the current implementation; it does not create mentor earnings.

---

## Store

SkillSwap includes a built-in product marketplace.

### Product Management

Products support:

- Product name
- Description
- Category
- Price
- Stock
- Image
- Active/inactive state
- Owner

### Shopping Flow

```text
Product
  ↓
Add to Cart
  ↓
Cart
  ↓
Checkout
  ↓
Demo Payment
  ↓
Order
  ↓
Order History / Order Details
```

The store also includes:

- Product categories
- Cart management
- Quantity updates
- Stock control
- Order records
- Order status management
- Platform commission and seller earning records

---

## Premium Plans

The project contains a premium subscription system.

Admins can:

- Create premium plans
- Set prices
- Set duration
- Add descriptions/features
- Activate/deactivate plans

Learners and mentors can view available premium plans and activate them through the demo payment flow.

Subscriptions store:

- User
- Plan
- Amount
- Start date
- Expiry date
- Status
- Payment reference
- Premium plan reference

---

## Notifications & Chat

### Chat

SkillSwap provides one-to-one mentor-learner chat for active learning relationships.

The current implementation uses secure polling rather than a WebSocket server.

Admins can also access relationship chat in **read-only monitoring mode**.

### Notifications

Notifications are generated for events such as:

- New learning requests
- Request acceptance/rejection
- Relationship creation
- Chat messages
- Learning plan updates
- Progress updates
- Learning completion
- Payment requests
- Payment success/failure
- Overdue payments
- Reviews
- Profile unlock
- Store activity
- Subscription activity
- Account status changes

The navbar displays unread notification counts and recent notifications.

---

## Admin Dashboard

The admin dashboard provides platform-level monitoring and management.

### Learning

- Active skills
- Active mentor-learner relationships
- Reviews
- Suspended users
- Relationship monitoring
- Relationship details
- Learning progress

### Business

- Successful payments
- Net platform revenue
- Pending withdrawals
- Store orders
- Store products

### User Management

Admins can review:

- Learners
- Mentors
- Pending applications
- Account status
- Verification documents
- User details

### Withdrawal Management

Admins can view and manage mentor withdrawal requests and update their status through the withdrawal workflow.

### Revenue

Revenue records distinguish different sources, including mentor payments, profile unlocks, subscriptions, and other platform revenue sources recorded by the application.

---

## AI Recommendation System

The project includes `services/ai_recommendation.py` for mentor recommendation logic.

The service contains functionality for:

- Geographic distance calculation using the Haversine formula
- Mentor fitness evaluation
- Experience scoring
- Hill-climbing search
- Simulated annealing
- A* search/navigation graph utilities
- Mentor recommendation generation

The recommendation endpoint is available through:

```text
/api/ai-recommend
```

It is protected by login requirements.

---

## Authentication & Security

The application includes several security controls.

### Authentication

- Password hashing using Werkzeug
- Session-based authentication
- Role-based authorization
- Separate admin login
- Account approval states
- Suspended/rejected account handling

### CSRF Protection

POST requests are protected by the application's CSRF token mechanism.

### Role Authorization

Routes use decorators such as:

```python
@role_required("Learner")
@role_required("Mentor")
@role_required("Admin")
```

### Verification Documents

Identity/certificate documents are stored under:

```text
private_uploads/
```

They are not intended to be publicly served from `static/` and are accessible only through authorized routes.

### Upload Security

Uploads use:

- Generated filenames
- Extension validation
- MIME validation
- Configurable upload size limits

### Sensitive Data

- Passwords are stored as hashes.
- `.env` should never be committed.
- Private verification documents should never be committed.
- Card CVV is not stored by the withdrawal model.
- Displayed account/card information is masked where appropriate.

For deployment, use HTTPS and configure:

```text
SESSION_COOKIE_SECURE=1
```

---

## Technology Stack

### Backend

- Python
- Flask 3.1.2
- Flask-SQLAlchemy 3.1.1
- Flask-Login 0.6.3
- PyMySQL 1.1.2
- python-dotenv
- Werkzeug security utilities

### Database

- MySQL 8.4
- SQLAlchemy ORM

### Frontend

- Jinja2 templates
- HTML5
- CSS3
- JavaScript
- Bootstrap-based responsive UI

### Deployment / Runtime

- Docker
- Docker Compose
- Gunicorn dependency for production WSGI deployment

No Node.js frontend is required.

---

## Project Structure

```text
SkillSwap/
│
├── app.py
├── config.py
├── extensions.py
├── wsgi.py
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example
│
├── database/
│   └── skillswap.sql
│
├── decorators/
│   └── auth.py
│
├── models/
│   ├── __init__.py
│   ├── auth.py
│   ├── connection.py
│   ├── learning.py
│   ├── reviews.py
│   └── store.py
│
├── routes/
│   ├── admin.py
│   ├── auth.py
│   ├── connections.py
│   ├── discovery.py
│   ├── learning.py
│   ├── payments.py
│   ├── premium.py
│   ├── profiles.py
│   ├── public.py
│   ├── reviews.py
│   └── store.py
│
├── services/
│   ├── ai_recommendation.py
│   ├── notifications.py
│   ├── payments.py
│   ├── premium.py
│   ├── revenue.py
│   ├── security.py
│   └── uploads.py
│
├── templates/
│   ├── admin/
│   ├── auth/
│   ├── connections/
│   ├── learner/
│   ├── learning/
│   ├── mentor/
│   ├── payments/
│   ├── premium/
│   ├── reviews/
│   ├── skills/
│   ├── store/
│   └── public/
│
├── static/
│   ├── css/
│   ├── js/
│   └── images/
│
├── private_uploads/
│   └── verification/
│
└── scratch/
    └── feature/test scripts
```

---

## Database

The application uses SQLAlchemy models for the main platform entities.

Important model groups include:

### Authentication & Profiles

- `Role`
- `User`
- `Location`
- `LearnerProfile`
- `MentorProfile`
- `Skill`
- `LearnerSkill`
- `MentorSkill`
- `VerificationDocument`

### Learning & Connections

- `LearningRequest`
- `LearningRelationship`
- `Conversation`
- `Message`
- `Notification`
- `LearningPlan`
- `LearningProgress`

### Payments

- `Payment`
- `PaymentTransaction`
- `Withdrawal`
- `MentorProfileAccess`
- `PlatformSetting`
- `Subscription`

### Reviews & Revenue

- `Review`
- `RevenueRecord`
- `PremiumPlan`

### Store

- `ProductCategory`
- `Product`
- `Cart`
- `CartItem`
- `Order`
- `OrderItem`

The application uses `db.create_all()` plus additive schema upgrade logic for compatibility with existing databases. A migration framework such as Alembic is not currently used.

---

## Installation

### 1. Clone the project

```powershell
git clone <repository-url>
cd SkillSwap
```

### 2. Create a virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```powershell
pip install -r requirements.txt
```

### 4. Create the environment file

```powershell
Copy-Item .env.example .env
```

Configure the MySQL credentials and application secret in `.env`.

### 5. Initialize the database

```powershell
flask --app app init-db
```

### 6. Create the admin account

Set `ADMIN_EMAIL` and an `ADMIN_PASSWORD` of at least 12 characters in `.env`, then run:

```powershell
flask --app app seed-admin
```

### 7. Start Flask

```powershell
flask --app app run --debug
```

The application will normally be available at:

```text
http://127.0.0.1:5000
```

---

## Docker Setup

The project includes Docker Compose for Flask + MySQL.

### 1. Create `.env`

```powershell
Copy-Item .env.example .env
```

### 2. Start the containers

```powershell
docker compose up -d
```

For a rebuild:

```powershell
docker compose up --build -d
```

The application is available at:

```text
http://localhost:5000
```

### Check container status

```powershell
docker compose ps
```

### View web logs

```powershell
docker compose logs -f web
```

### Stop containers

```powershell
docker compose down
```

The Compose configuration uses a MySQL health check and makes the Flask service depend on the database becoming healthy.

During development, the project directory is live-mounted into the web container, so Python/template/CSS/JavaScript changes can be reflected without rebuilding the image. Rebuild when changing `requirements.txt` or the `Dockerfile`.

---

## Useful Commands

### Initialize/upgrade database

```powershell
flask --app app init-db
flask --app app upgrade-db
```

### Verify database connection

```powershell
flask --app app check-db
```

### Seed admin

```powershell
flask --app app seed-admin
```

### Seed demo data

```powershell
flask --app app seed-demo
```

### Python syntax check

```powershell
python -m compileall -q app.py models routes services
```

### Dependency check

```powershell
python -m pip check
```

### Docker Compose validation

```powershell
docker compose config --quiet
```

---

## Testing & Validation

The repository contains feature-oriented scripts under `scratch/`, including checks for areas such as:

- Active learning cards
- Admin dashboard restoration
- Admin learning relationships
- AI recommendation authentication
- Homepage skill autocomplete
- Learning progress UI
- Mentor active learners
- Mentor profile unlock
- Notifications
- Reviews
- Terms & Regulations flow

The project also supports an application testing configuration that can use an isolated SQLite database when a local MySQL service is unavailable.

Before deployment, at minimum run:

```powershell
python -m compileall -q app.py models routes services
python -m pip check
docker compose config --quiet
```

---

## Demo Flow

A complete demonstration can follow this sequence:

1. Start MySQL/Flask or Docker Compose.
2. Seed the Admin account.
3. Register a learner and a mentor.
4. Accept the Terms & Regulations during signup.
5. Submit the accounts for verification.
6. Log in as Admin and approve the applications.
7. Log in as Learner.
8. Update learner interests.
9. Search mentors by skill/location.
10. Open an approved mentor profile.
11. Send a learning request.
12. Log in as Mentor and accept the request.
13. Create a learning plan.
14. Start chat and exchange messages.
15. Update learning progress.
16. Create a payment request/invoice.
17. Log in as Learner and pay through the demo payment flow.
18. Confirm the payment appears in the mentor's earnings.
19. Complete the learning relationship.
20. Submit a 1–5 star review and written feedback.
21. Log in as Mentor and view the review and earnings.
22. Submit a withdrawal request.
23. Log in as Admin and process/complete/reject the withdrawal.
24. Test the SkillSwap store and order flow.
25. Test premium plan activation.
26. Return to Admin to review relationships, payments, reviews, withdrawals, store activity, and revenue.

---

## Configuration

Environment variables are defined through `.env` / `.env.example`.

Important configuration areas include:

```text
FLASK_ENV
SECRET_KEY
DATABASE_URL
MYSQL_HOST
MYSQL_PORT
MYSQL_DATABASE
MYSQL_USER
MYSQL_PASSWORD
MYSQL_ROOT_PASSWORD
ADMIN_EMAIL
ADMIN_PASSWORD
SESSION_COOKIE_SECURE
```

Do not hardcode production credentials in source code.

---

## Important Payment Note

This project is currently an academic/demo implementation of a marketplace and mentorship platform.

The following are **not real financial transactions** in the current version:

- Mentor/learner payments
- Profile unlock payments
- Premium subscription payments
- Store checkout payments
- Mentor withdrawal processing

The application records these actions internally so the full platform workflow can be demonstrated.

For production use, the demo payment provider should be replaced with a real payment gateway and secure webhook verification. Withdrawal processing should also be connected to a legitimate payout provider or controlled financial workflow.

---

## Known Limitations

- Payments use a demo provider and do not process real money.
- Withdrawals are recorded and administratively processed inside the application rather than sent automatically to a real payout network.
- Chat uses polling rather than WebSockets.
- Geographic coordinates currently rely on stored values and known city/area mappings where applicable.
- A full external mapping/distance provider is not required for the current MVP.
- Database schema changes are handled by additive upgrade helpers rather than a dedicated migration framework.
- Production payment, payout, webhook, fraud, and compliance systems are not included.

---

## Future Improvements

Potential production-level improvements include:

- Integrate a real payment gateway.
- Integrate real bKash/Nagad/Rocket/bank payout APIs where legally and technically available.
- Add webhook verification and idempotency for payments.
- Replace polling chat with WebSockets.
- Add Alembic/Flask-Migrate for database migrations.
- Add automated unit/integration tests with a standard test runner.
- Add richer mentor recommendation and ranking evaluation.
- Add a proper mapping service for distance-based discovery.
- Add stronger audit logging for financial actions.
- Add production-grade rate limiting and abuse prevention.
- Add more detailed financial reconciliation and reporting.

---

## License

No explicit open-source license is defined in the current project files. Add a license file before distributing the project publicly if required.

---

## Project Status

**SkillSwap is a functional academic/MVP-style Flask application with integrated mentorship, learning, payment-record, review, store, premium, notification, withdrawal, and admin workflows.**

The current implementation is suitable for demonstration and further development, but real financial processing and production deployment require additional infrastructure, security, compliance, and payment-provider integration.
