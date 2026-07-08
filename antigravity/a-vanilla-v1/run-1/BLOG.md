# Building a Premium Library Tracker with Tina4 Python

In this post, we'll walk through the process of building **BookStack** — a lightweight, premium book-tracking web application built with the **Tina4 Python** framework and SQLite. 

BookStack enables users to easily manage a collection of books with full CRUD operations through both a sleek web interface and a structured JSON REST API.

---

## Technical Stack & Architecture

Tina4 is a zero-boilerplate, batteries-included web framework emphasizing convention over configuration. The application is structured as follows:

```
run-1/
├── app.py                      # Main application entry point
├── .env                        # Environment variable configuration
├── BLOG.md                     # Blog post (this file)
├── migrations/                 # Database schema migrations
│   └── 20260707110004_create_books_table.sql
└── src/
    ├── orm/
    │   └── Book.py             # Book ORM model class
    ├── routes/
    │   ├── books_api.py        # REST API endpoints (GET, POST, PUT, DELETE)
    │   └── web.py              # Page routing for the UI (/)
    ├── templates/
    │   ├── base.twig           # Base layout template
    │   └── books.twig          # Books tracker page view template
    └── scss/
        └── app.scss            # Custom SCSS styling (auto-compiles to CSS)
```

---

## How It Works

### 1. Database & Migrations
The database schema is defined in a migration SQL file (`migrations/20260707110004_create_books_table.sql`) rather than being executed programmatically. Tina4 tracks applied migrations in a dedicated table `tina4_migration`, ensuring they run exactly once.
We run migrations using the framework's CLI:
```bash
tina4 migrate
```

### 2. Active Record ORM
The `Book` record is defined in `src/orm/Book.py` by extending Tina4's `ORM` class:
```python
from tina4_python import ORM, IntegerField, StringField

class Book(ORM):
    table_name = "books"
    id = IntegerField(primary_key=True, auto_increment=True)
    title = StringField()
    author = StringField()
    published_year = IntegerField()
```
Tina4 auto-binds this model to the SQLite database connection string configured in our `.env`:
```env
TINA4_DATABASE_URL=sqlite:///data/books.db
```

### 3. REST API & Public Endpoints
We created five JSON API endpoints under `src/routes/books_api.py`:
- `GET /api/books` — list all books
- `GET /api/books/{id}` — fetch a single book
- `POST /api/books` — create a new book
- `PUT /api/books/{id}` — update a book's fields
- `DELETE /api/books/{id}` — delete a book

By default, Tina4 enforces authorization headers (Bearer token) for all `POST`, `PUT`, and `DELETE` requests to prevent unauthorized mutations. Since these are public API routes, we bypassed authentication using the `@noauth()` decorator:
```python
from tina4_python.core.router import post, noauth

@noauth()
@post("/api/books")
async def create_book(request, response):
    # data is read from request.body, validated, and saved
```

### 4. Interactive Web Interface
The home page (`/`) retrieves all books from the database and renders them through a Twig-compatible Jinja2 template (`src/templates/books.twig`):
- **Glassmorphic Cards**: Each book is represented as a glassmorphic card with subtle glow borders and hover translate animations.
- **AJAX Interactions**: Rather than traditional full-page reloads, adding, editing, or deleting a book triggers background `fetch()` requests and handles UI updates dynamically.
- **Real-Time Client-side Filtering**: Users can search books instantly by title, author, or year as they type.

---

## Technical Design Choices

1. **SQLite Database**: SQLite was chosen for local persistence because it requires no external server setup, runs entirely in a local file (`data/books.db`), and persists records reliably across app restarts.
2. **Explicit Port Binding**: The application binds to port `7011` as specified by the requirements, which is controlled dynamically by passing `-p 7011` to `tina4 serve`.
3. **Decoupled API & Web Controllers**: Placing REST routes in `books_api.py` and front-end page routes in `web.py` keeps code separated, clean, and maintainable.
4. **Rich Dark Aesthetics**: Moving away from standard white backgrounds, the app employs a curated dark layout (`#090d16`) with violet accents (`#8b5cf6`), modern Outfit typography, and glowing micro-animations to create a premium, state-of-the-art user experience.
