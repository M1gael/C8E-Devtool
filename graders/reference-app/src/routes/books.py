from tina4_python.core.router import get, post, put, delete, noauth

from src.orm.Book import Book


@get("/")
async def book_list_page(request, response):
    books = Book.select(limit=1000)
    return response.render("books.twig", {"books": [b.to_dict() for b in books]})


@get("/api/books")
async def list_books(request, response):
    return response(Book().select(limit=1000))


@get("/api/books/{id:int}")
async def get_book(id, request, response):
    book = Book.find(id)
    if book is None:
        return response({"error": "Book not found"}, 404)
    return response(book)


@noauth()
@post("/api/books")
async def create_book(request, response):
    book = Book(request.body)
    book.save()
    return response(book, 201)


@noauth()
@put("/api/books/{id:int}")
async def update_book(id, request, response):
    book = Book.find(id)
    if book is None:
        return response({"error": "Book not found"}, 404)
    for field in ("title", "author", "published_year"):
        if field in request.body:
            setattr(book, field, request.body[field])
    book.save()
    return response(book)


@noauth()
@delete("/api/books/{id:int}")
async def delete_book(id, request, response):
    book = Book.find(id)
    if book is None:
        return response({"error": "Book not found"}, 404)
    book.delete()
    return response("", 204)
