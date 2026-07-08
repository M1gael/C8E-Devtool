from tina4_python.core.router import get, post, put, delete, noauth
from src.orm.Book import Book
from src.orm.Loan import Loan
from src.orm.AuditLog import AuditLog
from tina4_python.orm import ORM
from datetime import datetime
import json

from src.app.helpers import get_current_staff, log_change

@noauth()
@get("/api/books")
async def list_books(request, response):
    db = ORM._get_db()
    q = request.params.get("q", "").strip()
    page = int(request.params.get("page", 1))
    limit = int(request.params.get("limit", 12))
    
    if page < 1:
        page = 1
    if limit < 1:
        limit = 12
        
    offset = (page - 1) * limit

    where_clauses = []
    params = []
    if q:
        where_clauses.append("(title LIKE ? OR author LIKE ? OR CAST(published_year AS TEXT) LIKE ? OR isbn LIKE ?)")
        search_pattern = f"%{q}%"
        params.extend([search_pattern, search_pattern, search_pattern, search_pattern])

    where_sql = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""
    
    # Get total count
    count_row = db.fetch_one("SELECT count(*) as total FROM book" + where_sql, params)
    total_records = count_row.get("total", 0) if count_row else 0
    total_pages = (total_records + limit - 1) // limit

    # Get page records
    books_query = f"SELECT * FROM book {where_sql} ORDER BY id DESC LIMIT ? OFFSET ?"
    query_params = params + [limit, offset]
    books_res = db.fetch(books_query, query_params)
    
    books = []
    for row in books_res.records:
        # Check availability
        active_loan = db.fetch_one("SELECT id FROM loan WHERE book_id = ? AND returned = 0", [row["id"]])
        row["is_available"] = 1 if not active_loan else 0
        books.append(row)

    return response({
        "books": books,
        "pagination": {
            "current_page": page,
            "limit": limit,
            "total_records": total_records,
            "total_pages": total_pages
        }
    })

@noauth()
@get("/api/books/{id:int}")
async def get_book(id, request, response):
    db = ORM._get_db()
    book = db.fetch_one("SELECT * FROM book WHERE id = ?", [id])
    if not book:
        return response({"error": "Not Found", "message": f"Book with ID {id} not found"}, 404)

    # Check availability
    active_loan = db.fetch_one("SELECT * FROM loan WHERE book_id = ? AND returned = 0", [id])
    book["is_available"] = 1 if not active_loan else 0
    
    # Get active loan details if borrowed
    current_loan = None
    if active_loan:
        member = db.fetch_one("SELECT name, email FROM member WHERE id = ?", [active_loan["member_id"]])
        current_loan = {
            "id": active_loan["id"],
            "member_id": active_loan["member_id"],
            "member_name": member["name"] if member else "Unknown",
            "borrow_date": active_loan["borrow_date"],
            "due_date": active_loan["due_date"]
        }

    # Get borrowing history
    loans_res = db.fetch(
        "SELECT l.*, m.name as member_name, m.email as member_email FROM loan l JOIN member m ON l.member_id = m.id WHERE l.book_id = ? ORDER BY l.id DESC",
        [id]
    )
    loans = loans_res.records

    return response({
        "book": book,
        "current_loan": current_loan,
        "loans": loans
    })

@post("/api/books")
async def create_book(request, response):
    staff = get_current_staff(request)
    if not staff:
        return response({"error": "Unauthorized", "message": "Valid staff session or token required"}, 401)

    body = request.body or {}
    title = body.get("title", "").strip()
    author = body.get("author", "").strip()
    published_year = body.get("published_year")
    isbn = body.get("isbn", "").strip()
    cover_image = body.get("cover_image", "").strip()

    # Validate inputs
    errors = []
    if not title:
        errors.append("Title is required")
    if not author:
        errors.append("Author is required")
    if not published_year:
        errors.append("Published year is required")
    else:
        try:
            year = int(published_year)
            if year < 1000 or year > 2100:
                errors.append("Published year must be between 1000 and 2100")
        except ValueError:
            errors.append("Published year must be a valid integer")
    if not isbn:
        errors.append("ISBN is required")

    if errors:
        return response({"error": "Validation Error", "message": "; ".join(errors)}, 400)

    # Insert book
    db = ORM._get_db()
    db.execute(
        "INSERT INTO book (title, author, published_year, isbn, cover_image) VALUES (?, ?, ?, ?, ?)",
        [title, author, int(published_year), isbn, cover_image or None]
    )
    db.commit()
    
    new_book = db.fetch_one("SELECT * FROM book WHERE isbn = ? ORDER BY id DESC LIMIT 1", [isbn])
    book_id = new_book["id"] if new_book else 0

    # Log action
    log_change(staff["staff_id"], "add_book", "book", book_id, {
        "title": title,
        "author": author,
        "published_year": int(published_year),
        "isbn": isbn
    })

    return response({"message": "Book added successfully", "book_id": book_id}, 201)

@put("/api/books/{id:int}")
@post("/api/books/{id:int}")
async def update_book(id, request, response):
    staff = get_current_staff(request)
    if not staff:
        return response({"error": "Unauthorized", "message": "Valid staff session or token required"}, 401)

    db = ORM._get_db()
    book = db.fetch_one("SELECT * FROM book WHERE id = ?", [id])
    if not book:
        return response({"error": "Not Found", "message": f"Book with ID {id} not found"}, 404)

    body = request.body or {}
    title = body.get("title", "").strip()
    author = body.get("author", "").strip()
    published_year = body.get("published_year")
    isbn = body.get("isbn", "").strip()
    cover_image = body.get("cover_image", "").strip()

    # Validate inputs
    errors = []
    if not title:
        errors.append("Title is required")
    if not author:
        errors.append("Author is required")
    if not published_year:
        errors.append("Published year is required")
    else:
        try:
            year = int(published_year)
            if year < 1000 or year > 2100:
                errors.append("Published year must be between 1000 and 2100")
        except ValueError:
            errors.append("Published year must be a valid integer")
    if not isbn:
        errors.append("ISBN is required")

    if errors:
        return response({"error": "Validation Error", "message": "; ".join(errors)}, 400)

    # Update book
    db.execute(
        "UPDATE book SET title = ?, author = ?, published_year = ?, isbn = ?, cover_image = ? WHERE id = ?",
        [title, author, int(published_year), isbn, cover_image or None, id]
    )
    db.commit()

    # Log action
    log_change(staff["staff_id"], "edit_book", "book", id, {
        "title": title,
        "author": author,
        "published_year": int(published_year),
        "isbn": isbn
    })

    return response({"message": "Book updated successfully"})

@delete("/api/books/{id:int}")
async def delete_book_endpoint(id, request, response):
    staff = get_current_staff(request)
    if not staff:
        return response({"error": "Unauthorized", "message": "Valid staff session or token required"}, 401)

    db = ORM._get_db()
    book = db.fetch_one("SELECT * FROM book WHERE id = ?", [id])
    if not book:
        return response({"error": "Not Found", "message": f"Book with ID {id} not found"}, 404)

    # Check if there are active loans
    active_loan = db.fetch_one("SELECT id FROM loan WHERE book_id = ? AND returned = 0", [id])
    if active_loan:
        return response({"error": "Conflict", "message": "Cannot delete a book that is currently out on loan"}, 409)

    # Delete book and its loan history
    db.execute("DELETE FROM book WHERE id = ?", [id])
    db.execute("DELETE FROM loan WHERE book_id = ?", [id])
    db.commit()

    # Log action
    log_change(staff["staff_id"], "remove_book", "book", id, {
        "title": book["title"],
        "author": book["author"]
    })

    return response({"message": "Book deleted successfully"})
