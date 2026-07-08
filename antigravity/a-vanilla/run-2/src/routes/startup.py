from tina4_python.core.events import once
from tina4_python.service import ServiceRunner
from tina4_python.debug import Log
from src.services.email_worker import EmailWorker
from src.orm.staff import Staff
from src.orm.book import Book
from src.orm.member import Member
import datetime

@once("app.ready")
def on_app_ready(payload):
    Log.info("Application is ready. Running startup initialization...")
    
    # 1. Start background Email Worker thread
    try:
        runner = ServiceRunner()
        runner.register("email_worker", EmailWorker(), daemon=True)
        runner.start()
        Log.info("Background EmailWorker started successfully.")
    except Exception as e:
        Log.error(f"Failed to start background EmailWorker: {e}")

    # 2. Seed default staff member if none exist
    try:
        staff_count = Staff.count()
        if staff_count == 0:
            staff = Staff()
            staff.name = "Librarian"
            staff.email = "staff@library.com"
            staff.set_password("password123")
            staff.save()
            Log.info("Default staff member seeded: staff@library.com / password123")
        else:
            Log.info(f"Staff table already has {staff_count} records.")
    except Exception as e:
        Log.error(f"Failed to seed staff: {e}")

    # 3. Seed books if catalog is empty
    try:
        book_count = Book.count()
        if book_count == 0:
            books_data = [
                {
                    "title": "The Hobbit",
                    "author": "J.R.R. Tolkien",
                    "published_year": 1937,
                    "isbn": "9780261102217",
                    "cover_image": "https://covers.openlibrary.org/b/isbn/9780261102217-L.jpg"
                },
                {
                    "title": "To Kill a Mockingbird",
                    "author": "Harper Lee",
                    "published_year": 1960,
                    "isbn": "9780446310789",
                    "cover_image": "https://covers.openlibrary.org/b/isbn/9780446310789-L.jpg"
                },
                {
                    "title": "1984",
                    "author": "George Orwell",
                    "published_year": 1949,
                    "isbn": "9780451524935",
                    "cover_image": "https://covers.openlibrary.org/b/isbn/9780451524935-L.jpg"
                },
                {
                    "title": "The Great Gatsby",
                    "author": "F. Scott Fitzgerald",
                    "published_year": 1925,
                    "isbn": "9780743273565",
                    "cover_image": "https://covers.openlibrary.org/b/isbn/9780743273565-L.jpg"
                }
            ]
            for b_data in books_data:
                book = Book()
                book.title = b_data["title"]
                book.author = b_data["author"]
                book.published_year = b_data["published_year"]
                book.isbn = b_data["isbn"]
                book.cover_image = b_data["cover_image"]
                book.save()
            Log.info("Default library catalog books seeded.")
        else:
            Log.info(f"Books catalog already has {book_count} records.")
    except Exception as e:
        Log.error(f"Failed to seed books: {e}")

    # 4. Seed members if empty
    try:
        member_count = Member.count()
        if member_count == 0:
            members_data = [
                {"name": "Alice Johnson", "email": "alice@example.com"},
                {"name": "Bob Smith", "email": "bob@example.com"}
            ]
            for m_data in members_data:
                member = Member()
                member.name = m_data["name"]
                member.email = m_data["email"]
                member.join_date = datetime.date.today().strftime("%Y-%m-%d")
                member.save()
            Log.info("Default members seeded.")
        else:
            Log.info(f"Members table already has {member_count} records.")
    except Exception as e:
        Log.error(f"Failed to seed members: {e}")
