# Building Lend — A Community Lending Library Application

Lend is a community lending-library application built using the **Tina4 Python** framework. It acts both as an interactive, fully localized website and a secure JSON API.

## Features Built

1. **Book & Member Catalogue**: Supports full CRUD operations (create, read, update, delete) for books and library members.
2. **Availability & History Tracking**: Tracks whether a book is available or currently borrowed, and displays a complete, chronological borrow history for each book.
3. **Staff Authentication**: Protects book, member, and loan actions with JWT-based Bearer token authentication and cookie-backed sessions.
4. **Audit Logging**: Automatically records every database modification (insert, update, delete, loan, return) and attributes the change to the staff member who authorized it.
5. **Asynchronous Email Receipts**: Uses a SQLite database-backed Tina4 Queue to immediately return HTTP responses to the staff recorder, while processing and writing borrower receipt emails asynchronously in the background.
6. **Multi-language Interface**: Available in both English (`en`) and Spanish (`es`) with a language selector in the navbar that persists the choice across pages.
7. **Interactive API Documentation**: Serves automated Swagger API docs on `/swagger` for testing and reviewing API requests.

---

## Architectural Decisions & Key Choices

### 1. Database Persistence
We selected **SQLite3** as the storage engine (`data/lend.db`) to ensure that all book, member, loan, and audit data survives application restarts. It is fully contained in the current directory to obey the workspace isolation rules.

### 2. Request-Scoped Twig Translations
To provide localized text in Twig templates, we inject a request-scoped `t` translation callable into the template rendering context. This enables translations to adapt dynamically to the query param (`?lang=es`) or the session preference without race conditions on concurrent requests.

### 3. Background Queue and Worker Threading
Borrowing receipts are sent using Tina4's built-in `Queue` class with the `file` backend. When a loan is successfully recorded, the endpoint pushes a task to the queue and immediately returns a success status. A background task registered via `background(consume_emails, 2.0)` polls this queue every 2 seconds cooperatively in the asyncio event loop without blocking HTTP request execution.

### 4. Interactive Swagger Docs
By utilizing the framework's native decorators (`@get`, `@post`, `@secured`, `@noauth`), Tina4 automatically gathers route details and serves an interactive Swagger UI at `/swagger` referencing `/swagger/openapi.json`.

---

## How to Run It

### Setup Dependencies
First, ensure you have all dependencies synced via the local virtual environment:
```bash
uv sync
```

### Run in Development Configuration
Start the server in development mode (with live reloading, file watching, and logging level set to `ALL`):
```bash
tina4 serve -p 7013
```
Open [http://localhost:7013](http://localhost:7013) to browse the library.
Log in as staff using:
- **Email**: `staff@library.com`
- **Password**: `password123`

### Run in Production Configuration
To run in production mode (with debugging turned off, a real secret configured, and uvicorn backend enabled):
1. Set the environment in `.env`:
   ```env
   TINA4_DEBUG=false
   TINA4_ENV=production
   ```
2. Start the server using:
   ```bash
   tina4 serve -p 7013 --production
   ```

---

## Running the Automated Test Suite

We wrote an automated test suite under `tests/test_library.py` utilizing Python's native `unittest` library and in-memory mock request/response patterns to verify catalogue search, authentication gates, double-borrow collisions, audit logging, and queueing.

Run the test suite using:
```bash
python -m unittest tests/test_library.py
```
