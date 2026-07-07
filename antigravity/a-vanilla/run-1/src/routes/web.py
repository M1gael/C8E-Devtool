from tina4_python.core.router import get, template
from src.orm.Book import Book

@get("/")
@template("books.twig")
async def index_page(request, response):
    books = Book.select(limit=1000)
    books_data = [book.to_dict() for book in books]
    return {"books": books_data}
