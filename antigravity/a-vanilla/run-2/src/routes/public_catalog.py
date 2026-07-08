from tina4_python.core.router import get, noauth
from tina4_python.database.connection import Database
from src.orm.book import Book
from tina4_python.swagger import description, tags, example_response

@get("/api/books")
@noauth()
@tags("Catalog")
@description("Search and list books with pagination", "Browse and search books in the catalogue by title, author, or year.")
@example_response(200, {
    "books": [
        {"id": 1, "title": "The Hobbit", "author": "J.R.R. Tolkien", "published_year": 1937, "isbn": "9780261102217", "cover_image": "...", "available": True}
    ],
    "total": 1,
    "page": 1,
    "per_page": 10,
    "pages": 1
})
async def list_books_api(request, response):
    db = Database()
    
    q = request.params.get("q", "").strip()
    page = int(request.params.get("page", 1))
    limit = int(request.params.get("limit", 10))
    
    sql = "SELECT * FROM books WHERE 1=1"
    sql_count = "SELECT COUNT(*) as total FROM books WHERE 1=1"
    params = []
    
    if q:
        sql += " AND (title LIKE ? OR author LIKE ? OR CAST(published_year AS TEXT) = ? OR isbn = ?)"
        sql_count += " AND (title LIKE ? OR author LIKE ? OR CAST(published_year AS TEXT) = ? OR isbn = ?)"
        term = f"%{q}%"
        params.extend([term, term, q, q])
        
    count_res = db.fetch_one(sql_count, params)
    total_count = count_res["total"] if count_res else 0
    
    sql += " ORDER BY title ASC LIMIT ? OFFSET ?"
    offset = (page - 1) * limit
    records = db.fetch(sql, params + [limit, offset])
    
    books = []
    if records and hasattr(records, "records"):
        recs = records.records
    elif isinstance(records, list):
        recs = records
    else:
        recs = []
        
    for r in recs:
        book = Book()
        book.id = r["id"]
        book.title = r["title"]
        book.author = r["author"]
        book.published_year = r["published_year"]
        book.isbn = r["isbn"]
        book.cover_image = r.get("cover_image", "")
        
        b_dict = book.to_dict()
        b_dict["available"] = book.is_available()
        books.append(b_dict)
        
    pages = (total_count + limit - 1) // limit if limit > 0 else 1
    
    return response.json({
        "books": books,
        "total": total_count,
        "page": page,
        "per_page": limit,
        "pages": pages
    })

@get("/api/books/{id:int}")
@noauth()
@tags("Catalog")
@description("Get book details", "Retrieve book details including current availability and complete borrowing history.")
@example_response(200, {
    "id": 1,
    "title": "The Hobbit",
    "author": "J.R.R. Tolkien",
    "published_year": 1937,
    "isbn": "9780261102217",
    "cover_image": "...",
    "available": True,
    "history": []
})
@example_response(404, {"error": "Book not found."})
async def get_book_api(id, request, response):
    book = Book.find_by_id(id)
    if not book:
        return response.json({"error": "Book not found."}, 404)
        
    b_dict = book.to_dict()
    b_dict["available"] = book.is_available()
    b_dict["history"] = book.get_history()
    return response.json(b_dict)
