import math
from tina4_python.core.router import get, noauth
from tina4_python.database import Database
from src.app.utils import render_template

@noauth()
@get("/")
@get("/catalogue")
async def get_catalogue(request, response):
    """Renders the public catalog web page with search and pagination."""
    params = request.params or {}
    query = params.get("q", "").strip()
    page = int(params.get("page", 1))
    if page < 1:
        page = 1
        
    limit = 10
    offset = (page - 1) * limit
    
    db = Database()
    
    # Construct paginated SQL queries
    if query:
        search_param = f"%{query}%"
        # Total matching records count
        total_row = db.fetch_one(
            "SELECT COUNT(*) as total FROM books WHERE title LIKE ? OR author LIKE ? OR CAST(published_year AS TEXT) LIKE ?",
            [search_param, search_param, search_param]
        )
        total = total_row.get("total", 0) if total_row else 0
        
        # Paginated book records with availability flag (1 = available, 0 = borrowed)
        sql = """
            SELECT b.*,
                   CASE WHEN (SELECT COUNT(*) FROM loans l WHERE l.book_id = b.id AND l.returned = 0) > 0 THEN 0 ELSE 1 END as available
            FROM books b
            WHERE b.title LIKE ? OR b.author LIKE ? OR CAST(b.published_year AS TEXT) LIKE ?
            ORDER BY b.title ASC
            LIMIT ? OFFSET ?
        """
        result = db.fetch(sql, [search_param, search_param, search_param, limit, offset])
    else:
        total_row = db.fetch_one("SELECT COUNT(*) as total FROM books")
        total = total_row.get("total", 0) if total_row else 0
        
        sql = """
            SELECT b.*,
                   CASE WHEN (SELECT COUNT(*) FROM loans l WHERE l.book_id = b.id AND l.returned = 0) > 0 THEN 0 ELSE 1 END as available
            FROM books b
            ORDER BY b.title ASC
            LIMIT ? OFFSET ?
        """
        result = db.fetch(sql, [limit, offset])
        
    books = result.records if result else []
    total_pages = math.ceil(total / limit) if total > 0 else 1
    
    return render_template(request, response, "catalogue.twig", {
        "books": books,
        "query": query,
        "page": page,
        "total_pages": total_pages,
        "total_records": total
    })

@noauth()
@get("/api/catalogue")
async def api_get_catalogue(request, response):
    """JSON API endpoint for searching and paging through the catalogue."""
    params = request.params or {}
    query = params.get("q", "").strip()
    page = int(params.get("page", 1))
    if page < 1:
        page = 1
        
    limit = 10
    offset = (page - 1) * limit
    
    db = Database()
    
    if query:
        search_param = f"%{query}%"
        total_row = db.fetch_one(
            "SELECT COUNT(*) as total FROM books WHERE title LIKE ? OR author LIKE ? OR CAST(published_year AS TEXT) LIKE ?",
            [search_param, search_param, search_param]
        )
        total = total_row.get("total", 0) if total_row else 0
        
        sql = """
            SELECT b.*,
                   CASE WHEN (SELECT COUNT(*) FROM loans l WHERE l.book_id = b.id AND l.returned = 0) > 0 THEN 0 ELSE 1 END as available
            FROM books b
            WHERE b.title LIKE ? OR b.author LIKE ? OR CAST(b.published_year AS TEXT) LIKE ?
            ORDER BY b.title ASC
            LIMIT ? OFFSET ?
        """
        result = db.fetch(sql, [search_param, search_param, search_param, limit, offset])
    else:
        total_row = db.fetch_one("SELECT COUNT(*) as total FROM books")
        total = total_row.get("total", 0) if total_row else 0
        
        sql = """
            SELECT b.*,
                   CASE WHEN (SELECT COUNT(*) FROM loans l WHERE l.book_id = b.id AND l.returned = 0) > 0 THEN 0 ELSE 1 END as available
            FROM books b
            ORDER BY b.title ASC
            LIMIT ? OFFSET ?
        """
        result = db.fetch(sql, [limit, offset])
        
    books = result.records if result else []
    total_pages = math.ceil(total / limit) if total > 0 else 1
    
    return response.json({
        "books": books,
        "page": page,
        "limit": limit,
        "total": total,
        "total_pages": total_pages
    })

@noauth()
@get("/books/{id:int}")
async def get_book_details(id, request, response):
    """Renders the detailed page of a book with its current status and loan history."""
    db = Database()
    
    # Fetch book info
    book = db.fetch_one("SELECT * FROM books WHERE id = ?", [id])
    if not book:
        return response.redirect("/catalogue")
        
    # Check availability
    active_loan = db.fetch_one("SELECT * FROM loans WHERE book_id = ? AND returned = 0", [id])
    available = 0 if active_loan else 1
    
    # Fetch borrowing history
    history_sql = """
        SELECT l.*, m.name as member_name, m.email as member_email
        FROM loans l
        JOIN members m ON l.member_id = m.id
        WHERE l.book_id = ?
        ORDER BY l.borrow_date DESC
    """
    history_result = db.fetch(history_sql, [id])
    history = history_result.records if history_result else []
    
    return render_template(request, response, "book_detail.twig", {
        "book": book,
        "available": available,
        "active_loan": active_loan,
        "history": history
    })

@noauth()
@get("/api/books/{id:int}")
async def api_get_book_details(id, request, response):
    """JSON API endpoint returning book details, availability, and loan history."""
    db = Database()
    
    book = db.fetch_one("SELECT * FROM books WHERE id = ?", [id])
    if not book:
        return response.json({
            "error": "Not Found",
            "message": "Book not found"
        }, 404)
        
    # Check availability
    active_loan = db.fetch_one("SELECT * FROM loans WHERE book_id = ? AND returned = 0", [id])
    available = 0 if active_loan else 1
    
    # Fetch history
    history_sql = """
        SELECT l.*, m.name as member_name, m.email as member_email
        FROM loans l
        JOIN members m ON l.member_id = m.id
        WHERE l.book_id = ?
        ORDER BY l.borrow_date DESC
    """
    history_result = db.fetch(history_sql, [id])
    history = history_result.records if history_result else []
    
    # Construct complete payload
    payload = dict(book)
    payload["available"] = bool(available)
    payload["borrowing_history"] = history
    
    return response.json(payload)
