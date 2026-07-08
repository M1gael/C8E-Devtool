from tina4_python.core.router import get, post, put, delete, noauth
from src.orm.Book import Book

@get("/api/books")
async def list_books(request, response):
    books = Book.select(limit=1000)
    # response() auto-serializes list of ORM models to a JSON array
    return response(books)

@get("/api/books/{id:int}")
async def get_book(id, request, response):
    book = Book.find_by_id(id)
    if not book:
        return response({"error": "Book not found"}, 404)
    # response() auto-serializes a single ORM model to a JSON object
    return response(book)

@noauth()
@post("/api/books")
async def create_book(request, response):
    data = request.body
    if not data or "title" not in data or "author" not in data or "published_year" not in data:
        return response({"error": "Missing required fields: title, author, published_year"}, 400)
    
    try:
        published_year = int(data["published_year"])
    except (ValueError, TypeError):
        return response({"error": "published_year must be an integer"}, 400)
    
    book = Book(
        title=str(data["title"]),
        author=str(data["author"]),
        published_year=published_year
    )
    
    if not book.save():
        return response({"error": f"Failed to save book: {book.last_error}"}, 500)
    
    return response(book, 201)

@noauth()
@put("/api/books/{id:int}")
async def update_book(id, request, response):
    book = Book.find_by_id(id)
    if not book:
        return response({"error": "Book not found"}, 404)
    
    data = request.body
    if not data:
        return response({"error": "Request body is empty"}, 400)
    
    if "title" in data:
        book.title = str(data["title"])
    if "author" in data:
        book.author = str(data["author"])
    if "published_year" in data:
        try:
            book.published_year = int(data["published_year"])
        except (ValueError, TypeError):
            return response({"error": "published_year must be an integer"}, 400)
            
    if not book.save():
        return response({"error": f"Failed to update book: {book.last_error}"}, 500)
        
    return response(book)

@noauth()
@delete("/api/books/{id:int}")
async def delete_book(id, request, response):
    book = Book.find_by_id(id)
    if not book:
        return response({"error": "Book not found"}, 404)
        
    try:
        book.delete()
    except Exception as e:
        return response({"error": f"Failed to delete book: {str(e)}"}, 500)
        
    return response({"success": True})
