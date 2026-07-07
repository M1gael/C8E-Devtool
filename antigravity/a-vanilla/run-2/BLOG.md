# BookStack: Building a Premium Library Tracker with Tina4 Python

In this post, we walk through the design and implementation of **BookStack** — a modern, premium library manager and book-tracking web application built with the **Tina4 Python** framework and SQLite.

BookStack allows readers and librarians to organize their book catalogs with ease, offering a high-fidelity visual experience, client-side real-time search, and a complete JSON REST API.

---

## The Technology Stack & Architecture

Tina4 Python is a lightweight ASGI web framework that leverages convention over configuration. It provides database migrations, a convention-based Active Record ORM, routing decorators, and a template engine out of the box.

The project structure is organized as follows:

```text
run-2/
├── app.py                      # ASGI Application Entrypoint
├── .env                        # Port and DB URL configuration (port 7012)
├── .env.local                  # Local debug environment secret
├── pyproject.toml              # Build & dependency configurations
├── BLOG.md                     # This blog post
├── migrations/                 # SQL Schema migration files
│   └── 20260707110004_create_books_table.sql
└── src/
    ├── orm/
    │   └── Book.py             # Book ORM Model
    ├── routes/
    │   ├── books_api.py        # REST API Router (GET, POST, PUT, DELETE)
    │   └── web.py              # Web View Page Router (/)
    ├── templates/
    │   ├── base.twig           # General layout template (CSS, fonts, JS)
    │   └── books.twig          # Premium book grid page template & AJAX scripts
    └── scss/
        └── app.scss            # Sass style source
```

---

## How It Works

### 1. Database Migrations
Rather than executing raw DDL code manually, we define a structured SQL migration script in `migrations/`. This migration runs reliably when using the Tina4 CLI:
```bash
tina4 migrate
```
The migration defines our schema:
```sql
CREATE TABLE books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    author TEXT NOT NULL,
    published_year INTEGER NOT NULL
);
```

### 2. Active Record ORM Mapping
The `Book` model maps directly to our database table by inheriting from Tina4's `ORM` class:
```python
from tina4_python import ORM, IntegerField, StringField

class Book(ORM):
    table_name = "books"
    id = IntegerField(primary_key=True, auto_increment=True)
    title = StringField()
    author = StringField()
    published_year = IntegerField()
```

### 3. REST API Routes
The router implements the standard CRUD JSON API under `/api/books`:
- `GET /api/books` — list all books
- `GET /api/books/{id}` — fetch a single book
- `POST /api/books` — create a book
- `PUT /api/books/{id}` — update a book
- `DELETE /api/books/{id}` — delete a book

By using the `@noauth()` decorator on modifying actions, we allow standard public HTTP requests:
```python
from tina4_python.core.router import get, post, put, delete, noauth
from src.orm.Book import Book

@get("/api/books")
async def list_books(request, response):
    books = Book.select(limit=1000)
    return response(books)
```

### 4. Templated Frontend View
The main page `/` handles frontend template rendering. It fetches all stored records, casts them to serializable dictionaries, and feeds them to `books.twig`.
- **Modals and AJAX Forms**: Adding or editing books is handled using modal elements and native JavaScript `fetch()` calls to keep mutations reactive without refreshing the whole page.
- **Client-Side Real-Time Filter**: A search box filters cards instantly based on title, author, or publication year as the user types.

---

## Technical Design Decisions

1. **SQLite for Persistence**: SQLite is lightweight and requires no separate setup, saving everything in a local file (`data/books.db`). This ensures that database records survive application restarts cleanly.
2. **Explicit Port Config**: The application uses environment variables in `.env` (`TINA4_PORT=7012`) to bind to port 7012.
3. **Glassmorphic and Dark Theme UI**: Instead of using plain backgrounds, the UI has a dark color palette (`#090d16` with purple/indigo glow gradients `#8b5cf6`), premium Outfit typography, subtle animations (fade-in, transform shifts, card hover scales), and toast alert boxes.
4. **Decoupled API & Web Controllers**: Routing is divided into `books_api.py` and `web.py` to keep backend APIs separate from presentation logic.
