import json
from tina4_python import get, post, put, delete, noauth
from src.orm.Book import Book

# Web Page Route
@get("/")
async def show_homepage(request, response):
    books = Book.all(limit=1000)
    books_data = [book.to_dict() for book in books]
    return response.render("books.twig", {"books": books_data})

# REST API - List all books
@get("/api/books")
async def list_books(request, response):
    books = Book.all(limit=1000)
    books_data = [book.to_dict() for book in books]
    return response.json(books_data)

# REST API - Get one book by ID
@get("/api/books/{id}")
async def get_book(id, request, response):
    try:
        book_id = int(id)
    except ValueError:
        return response.json({"error": "Invalid book ID"}, 400)
        
    book = Book.find_by_id(book_id)
    if book:
        return response.json(book.to_dict())
    else:
        return response.json({"error": "Book not found"}, 404)

# REST API - Create a book
@post("/api/books")
@noauth()
async def create_book(request, response):
    body = request.body
    if isinstance(body, (str, bytes)):
        try:
            body = json.loads(body)
        except Exception:
            return response.json({"error": "Invalid JSON body"}, 400)
            
    title = body.get("title")
    author = body.get("author")
    published_year = body.get("published_year")
    
    if not title or not author or published_year is None:
        return response.json({"error": "Missing required fields: title, author, published_year"}, 400)
        
    try:
        published_year = int(published_year)
    except ValueError:
        return response.json({"error": "published_year must be an integer"}, 400)
        
    book = Book(title=title, author=author, published_year=published_year)
    if book.save():
        return response.json(book.to_dict(), 201)
    else:
        error_msg = book.get_error() or "Failed to save book"
        return response.json({"error": error_msg}, 400)

# REST API - Update a book
@put("/api/books/{id}")
@noauth()
async def update_book(id, request, response):
    try:
        book_id = int(id)
    except ValueError:
        return response.json({"error": "Invalid book ID"}, 400)
        
    book = Book.find_by_id(book_id)
    if not book:
        return response.json({"error": "Book not found"}, 404)
        
    body = request.body
    if isinstance(body, (str, bytes)):
        try:
            body = json.loads(body)
        except Exception:
            return response.json({"error": "Invalid JSON body"}, 400)
            
    title = body.get("title")
    author = body.get("author")
    published_year = body.get("published_year")
    
    if title is not None:
        book.title = title
    if author is not None:
        book.author = author
    if published_year is not None:
        try:
            book.published_year = int(published_year)
        except ValueError:
            return response.json({"error": "published_year must be an integer"}, 400)
            
    if book.save():
        return response.json(book.to_dict())
    else:
        error_msg = book.get_error() or "Failed to update book"
        return response.json({"error": error_msg}, 400)

# REST API - Delete a book
@delete("/api/books/{id}")
@noauth()
async def delete_book(id, request, response):
    try:
        book_id = int(id)
    except ValueError:
        return response.json({"error": "Invalid book ID"}, 400)
        
    book = Book.find_by_id(book_id)
    if not book:
        return response.json({"error": "Book not found"}, 404)
        
    if book.delete():
        return response.json({"message": "Book deleted successfully"})
    else:
        return response.json({"error": "Failed to delete book"}, 400)
