# Building Lend: A Community Lending-Library App with Tina4 Python

Lend is a community lending-library web application and JSON API built with the **Tina4 Python** framework. Lend allows the public to browse and search a library catalogue of books, while library staff members sign in to register members, manage books, record loans and returns, and inspect detailed audit trails of system changes. 

Here is a breakdown of what was built, how the application was structured, and the key technical decisions made along the way.

---

## 🛠️ Architecture and Code Structure

Lend is designed around a clean, conventions-driven modular structure:

* **Entry Point (`app.py`)**: Runs the Tina4 web server on port 7032, imports routes and template settings, and initializes the background email queue worker.
* **Database & Migrations (`migrations/`)**: Contains SQLite DDL files defining the tables and seeding the initial staff account.
* **ORM Data Models (`src/orm/`)**: Implements `Staff`, `Book`, `Member`, `Loan`, and `AuditLog` Active Record models.
* **Authentication Helper (`src/app/auth.py`)**: Enforces access control by verifying JWT tokens (for API requests) and sessions/cookies (for HTML page loads).
* **Email Queue Daemon (`src/app/email_worker.py`)**: Continuously pops background tasks from a file-based queue to send transaction receipts asynchronously.
* **Rendering & Localization (`src/app/template.py`)**: Integrates Jinja2/Twig translation filters, supporting English (`en`) and Spanish (`es`) out of the box.
* **Route Handlers (`src/routes/`)**:
  * `api.py`: Houses REST JSON API endpoints.
  * `web.py`: Serves public HTML templates, handle forms, and redirect flows.
* **Premium Theme Styles (`src/scss/`)**: Uses SCSS to compile modern HSL color palettes, dark backgrounds, glassmorphism cards, and responsive components.

---

## 💡 Key Design & Implementation Decisions

### 1. Unified Authentication Flow
The prompt required that anyone who is not signed in must be refused from staff actions on both the website and the JSON API. 
* **Decision**: We created a unified helper function `get_authenticated_staff(request)`. First, it inspects the request's HTTP headers for a `Authorization: Bearer <token>` string and validates the JWT payload. If missing or invalid, it falls back to inspecting the request session cookie for `staff_id`.
* **Benefit**: This single function makes it trivial to secure write routes (POST/PUT/DELETE) for both AJAX/API consumers and traditional HTML form submissions. Route handlers decorate with `@noauth()` to bypass default framework-level Bearer requirements and call this helper manually to control unauthorized redirections or JSON errors.

### 2. Auto-Starting Queue Consumer Daemon
Lending receipts must be emailed to library members immediately upon borrowing a book without delaying the web response.
* **Decision**: We set up a background thread (`threading.Thread`) registered in the main entry point `app.py` before `run()` starts. The thread runs a loop that polls a SQLite/file-based Queue topic (`loan_emails`) every 2 seconds, processes enqueued jobs, sends emails via Tina4's built-in `Messenger` SMTP client, and calls `job.complete()`.
* **Benefit**: Because it is declared as a daemon thread directly inside the server's lifecycle, the background worker starts and stops automatically whenever `tina4 serve` is executed, removing the need for a separate worker CLI command.

### 3. Programmatic Test Database Isolation
We needed automated tests to prove book search pagination, access control checks, loan duplicate rejections, queuing, and audit logging.
* **Decision**: We wrote a pytest fixture in `tests/test_lend.py` that intercepts the ORM's active database connection and overrides it with an isolated sqlite database `data/test_lend.db` specifically for test runs. The fixture runs migrations to create a clean schema and seeds a test staff member. At the end of the test run, the test file is deleted.
* **Benefit**: This guarantees that tests run in total isolation, do not pollute the production/development database, and are 100% reproducible.

### 4. Locale Synchronization
The web client must support both English and Spanish, allowing seamless language toggles.
* **Decision**: The rendering helper `render()` checks for a `lang` parameter in the query string (e.g. `?lang=es`). If found, it updates the session language value. It then sets the current locale in the framework's `I18n` class before compiling the Twig template.
* **Benefit**: The user's language selection is remembered across pages in their session, and any translation code `{{ t("key") }}` in our HTML templates is dynamically localized automatically.

---

## 🚀 Running the Project

### Prerequisites
Make sure Python 3.12+ and `uv` package manager are installed.

### 1. Run Migrations & Start Server
Deploy the database tables and start the web application:
```bash
tina4 serve
```
The server will start on port `7032`.

### 2. Verify with Automated Tests
Execute the pytest unit test suite:
```bash
.venv\Scripts\python -m pytest tests/ -v
```
All 6 test cases covering book pagination, search, authentication blocks, duplicate loans, background email queues, and audit logs will execute and pass.
