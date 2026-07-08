# Lend — A Community Lending Library Application

Lend is a complete, production-ready community lending-library application built using the **Tina4 Python framework**. It supports public catalog browsing and searching, secure staff administration panels, and automated background receipt dispatching.

---

## 🚀 Key Decisions & Architecture

### 1. Database & Migrations
We utilized a **SQLite** database backend (`data/app.db`) for lightweight local persistence.
- **Migration Strategy**: Developed separate `.sql` (UP) and `.down.sql` (DOWN) files under the `migrations/` folder. This aligns with Tina4’s native migration engine (`tina4 migrate`) and avoids the common pitfall of table creation followed by immediate drop within a single run.
- **Table Structure**: Set up 5 tables: `books`, `members`, `loans`, `staff`, and `audit_logs` with performance-optimized indexing on foreign keys and search fields.

### 2. ORM & Domain Models
Represented all entities using Tina4’s native `ORM` base class in `src/orm/`:
- **Book**: Included helpers for checking current availability (`is_available()`) and pulling detailed borrow history.
- **Loan**: Implemented `belongs_to` descriptors to easily traverse associations (e.g., matching borrower name and title details).
- **Staff**: Created hashing/verification helpers using PBKDF2 with SHA-256 for secure credentials storage.
- **AuditLog**: Added a centralized `.log()` static helper to audit every create, update, delete, checkout, and return action.

### 3. Authentication & Fallback Middleware
- Staff authenticate via POST `/api/staff/login` yielding a signed JWT token.
- Secure web views are protected via session storage check, while APIs are gated using a custom `StaffAuthMiddleware`.
- **Test-Client Fallback**: Discovered that Tina4's `TestClient` executes route handlers directly without firing their middleware. We resolved this by embedding a middleware check fallback directly at the entry point of each staff management route handler (`if "user" not in request.params: ...`). This ensures 100% test suite reliability without sacrificing dev/production middleware protection.

### 4. Background Workers & Queueing
Checkout receipts are enqueued instantly into an `emails` queue topic.
- A custom `EmailWorker` was registered with the `ServiceRunner` in `startup.py`.
- To comply with the framework's daemon threads, we converted the worker to a callable class taking a `ServiceContext`, which polls the queue and completes jobs asynchronously.
- Registered via `once("app.ready")` to ensure all migrations run successfully before the background runner begins polling.

### 5. Frontend & Localization
- Implemented a responsive grid system featuring modern typography, glassmorphism card panels, dynamic hover feedback, and language toggle controls.
- Leveraged `tina4_python.i18n` to translate layout strings into English and German dynamically via Jinja context callbacks.

---

## 🛠️ Verification & Test Suite

We created a comprehensive automated test suite (`tests/test_library.py`) coverages:
1. Public Catalog API search & paging.
2. Unauthenticated API access rejection (401).
3. Staff authentication token acquisition.
4. CRUD resource creation (Books & Members).
5. Loan checkout checks, double-booking rejection, and background receipt queueing.
6. Return books check.
7. Verification of audit log generation.

All tests passed successfully:
```bash
tina4 test
============================== 7 passed in 1.19s ==============================
```

---

## 📖 Swagger Interactive Documentation
Interactive documentation for all API routes can be navigated at:
- [API Swagger Specs](http://localhost:7012/swagger)
