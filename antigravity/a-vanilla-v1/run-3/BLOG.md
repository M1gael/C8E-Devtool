# Building a Premium Book-Tracking Web App with Tina4 Python

In this post, we will explore the design and implementation of **BookStack**, a premium, dark-themed book management dashboard and JSON REST API built using the **Tina4 Python framework** (`tina4-python`) and SQLite.

## What We Built

We created a complete, end-to-end book-tracking system featuring:
1.  **A Clean SQLite Database Schema**: Mapped and instantiated using Tina4's native database migration mechanism.
2.  **A Dynamic JSON REST API**:
    *   `GET /api/books` — Retrieve all books from the database.
    *   `GET /api/books/{id}` — Fetch details for a specific book by ID.
    *   `POST /api/books` — Create a new book entry.
    *   `PUT /api/books/{id}` — Update details (title, author, published year) of a book.
    *   `DELETE /api/books/{id}` — Remove a book from the library.
3.  **An Interactive Dashboard (`/`)**: Rendered serverside via Twig templates, featuring:
    *   Real-time, client-side search filtering by book title, author, or year.
    *   Asynchronous modals for adding and editing book records (integrated with the REST API).
    *   Interactive toast notifications for success/error feedback.
    *   A premium, responsive dark-theme design utilizing CSS Grid, backdrop blur filters, and micro-animations.

---

## How It Works

### 1. Data Modeling & Persistence
We defined a `Book` class that inherits from Tina4's built-in `ORM`. The ORM maps class fields (`IntegerField`, `StringField`) to a `books` table in SQLite:

```python
from tina4_python import ORM, IntegerField, StringField

class Book(ORM):
    table_name = "books"
    id = IntegerField(primary_key=True, auto_increment=True)
    title = StringField()
    author = StringField()
    published_year = IntegerField()
```

The database table is created by running the schema migration file:
```sql
CREATE TABLE books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    author TEXT NOT NULL,
    published_year INTEGER NOT NULL
);
```

### 2. Request Routing & Parameter Mapping
Tina4 handles routing via decorators like `@get` and `@post`. 
An important discovery was the mapping of URL parameters: **Tina4 injects matched path variables first**, followed by the standard `request` and `response` objects. We structured our signatures accordingly to ensure proper mapping:

```python
@get("/api/books/{id}")
async def get_book(id, request, response):
    book = Book.find_by_id(int(id))
    # ...
```

### 3. Public API Endpoints
By default, Tina4 secures write routes (`POST`, `PUT`, `DELETE`). Since we wanted a public REST API for this tracking tool, we applied the `@noauth()` decorator to bypass auth gates for those endpoints:

```python
@post("/api/books")
@noauth()
async def create_book(request, response):
    # ...
```

### 4. Stylesheet Compilation
Tina4 features an integrated **SCSS compiler**. We structured our styles inside `src/scss/app.scss`, and the framework automatically compiled them into `src/public/css/app.css` when running the dev server (`tina4 serve`).

---

## Technical Decisions

*   **Tina4 Native ORM over SQLAlchemy**: To honor the framework's architecture and benefit from its optimized, built-in features (like transaction safety and request-scoped query caching), we opted for the native ORM.
*   **Decoupled Frontend Actions (Fetch API)**: Instead of traditional HTML form submissions which cause full-page refreshes, we built the modals to communicate with the JSON API asynchronously using `fetch()`. This results in a fast, fluid user experience.
*   **Real-time Client-Side Search**: Rather than making database queries on every keystroke, we implemented client-side DOM filtering based on search keywords. This decreases server load and gives immediate feedback to users.
*   **Persistent SQLite Storage**: The database is stored at `data/books.db`, ensuring that all added books survive application restarts and are safely written to disk.
