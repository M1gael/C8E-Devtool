from tina4_python.core.router import post, put, delete, get, middleware, secured
from src.routes.staff_auth import StaffAuthMiddleware
from src.orm.book import Book
from src.orm.member import Member
from src.orm.loan import Loan
from src.orm.audit_log import AuditLog
from tina4_python.queue import Queue
from tina4_python.swagger import description, tags, example, example_response
import datetime
import re

def validate_email(email):
    return re.match(r"^[^@]+@[^@]+\.[^@]+$", email) is not None

def validate_isbn(isbn):
    # Check if isbn is at least 10 digits/chars after stripping hyphens
    cleaned = isbn.replace("-", "").replace(" ", "")
    return len(cleaned) >= 10

# ----------------- BOOK CRUD -----------------

@middleware(StaffAuthMiddleware)
@post("/api/books")
@tags("Staff Management")
@description("Add a new book", "Add a new book to the library catalog. Staff authentication required.")
@example({"title": "1984", "author": "George Orwell", "published_year": 1949, "isbn": "978-0451524935", "cover_image": ""})
async def add_book(request, response):
    if "user" not in request.params:
        request, response = StaffAuthMiddleware.before_auth(request, response)
        if response.status_code >= 400:
            return response
    body = request.body
    if not body or not body.get("title") or not body.get("author") or not body.get("published_year") or not body.get("isbn"):
        return response.json({"error": "Title, author, published year, and ISBN are required."}, 400)
        
    try:
        year = int(body["published_year"])
    except ValueError:
        return response.json({"error": "Published year must be a valid number."}, 400)
        
    if not validate_isbn(body["isbn"]):
        return response.json({"error": "Invalid ISBN format."}, 400)
        
    book = Book()
    book.title = body["title"].strip()
    book.author = body["author"].strip()
    book.published_year = year
    book.isbn = body["isbn"].strip()
    book.cover_image = body.get("cover_image", "").strip()
    book.save()
    
    AuditLog.log(request.params["user"]["staff_id"], "add_book", {
        "book_id": book.id,
        "title": book.title,
        "author": book.author
    })
    
    return response.json({"message": "Book added successfully.", "book": book.to_dict()}, 201)

@middleware(StaffAuthMiddleware)
@put("/api/books/{id:int}")
@tags("Staff Management")
@description("Edit an existing book", "Modify book details. Staff authentication required.")
@example({"title": "1984 (Special Edition)", "author": "George Orwell", "published_year": 1949, "isbn": "978-0451524935", "cover_image": ""})
async def edit_book(id, request, response):
    if "user" not in request.params:
        request, response = StaffAuthMiddleware.before_auth(request, response)
        if response.status_code >= 400:
            return response
    book = Book.find_by_id(id)
    if not book:
        return response.json({"error": "Book not found."}, 404)
        
    body = request.body
    if not body:
        return response.json({"error": "Request body required."}, 400)
        
    if body.get("published_year"):
        try:
            book.published_year = int(body["published_year"])
        except ValueError:
            return response.json({"error": "Published year must be a valid number."}, 400)
            
    if body.get("isbn") and not validate_isbn(body["isbn"]):
        return response.json({"error": "Invalid ISBN format."}, 400)
        
    if body.get("title"):
        book.title = body["title"].strip()
    if body.get("author"):
        book.author = body["author"].strip()
    if body.get("isbn"):
        book.isbn = body["isbn"].strip()
    if "cover_image" in body:
        book.cover_image = body["cover_image"].strip()
        
    book.save()
    
    AuditLog.log(request.params["user"]["staff_id"], "edit_book", {
        "book_id": book.id,
        "title": book.title
    })
    
    return response.json({"message": "Book updated successfully.", "book": book.to_dict()})

@middleware(StaffAuthMiddleware)
@delete("/api/books/{id:int}")
@tags("Staff Management")
@description("Delete a book", "Remove a book from the catalog. Staff authentication required.")
async def delete_book(id, request, response):
    if "user" not in request.params:
        request, response = StaffAuthMiddleware.before_auth(request, response)
        if response.status_code >= 400:
            return response
    book = Book.find_by_id(id)
    if not book:
        return response.json({"error": "Book not found."}, 404)
        
    # Check if currently loaned out
    if not book.is_available():
        return response.json({"error": "Cannot delete book. It is currently loaned out."}, 400)
        
    book.delete()
    
    AuditLog.log(request.params["user"]["staff_id"], "delete_book", {
        "book_id": id,
        "title": book.title
    })
    
    return response.json({"message": "Book deleted successfully."})

# ----------------- MEMBER CRUD -----------------

@middleware(StaffAuthMiddleware)
@get("/api/members")
@tags("Staff Management")
@description("List all members", "Retrieve list of all library members. Staff authentication required.")
async def list_members(request, response):
    if "user" not in request.params:
        request, response = StaffAuthMiddleware.before_auth(request, response)
        if response.status_code >= 400:
            return response
    members = Member.all()
    
    m_list = []
    if members and hasattr(members, "records"):
        recs = members.records
    elif isinstance(members, list):
        recs = members
    else:
        recs = []
        
    for r in recs:
        if isinstance(r, Member):
            m_list.append(r.to_dict())
        else:
            m_list.append(r)
            
    return response.json(m_list)

@middleware(StaffAuthMiddleware)
@post("/api/members")
@tags("Staff Management")
@description("Add a library member", "Register a new library member. Staff authentication required.")
@example({"name": "John Doe", "email": "john@example.com"})
async def add_member(request, response):
    if "user" not in request.params:
        request, response = StaffAuthMiddleware.before_auth(request, response)
        if response.status_code >= 400:
            return response
    body = request.body
    if not body or not body.get("name") or not body.get("email"):
        return response.json({"error": "Name and email are required."}, 400)
        
    email = body["email"].strip().lower()
    if not validate_email(email):
        return response.json({"error": "Invalid email format."}, 400)
        
    # Check email uniqueness
    existing = Member.where("email = ?", [email])
    if existing:
        return response.json({"error": "Email is already registered to a member."}, 400)
        
    member = Member()
    member.name = body["name"].strip()
    member.email = email
    member.join_date = datetime.date.today().strftime("%Y-%m-%d")
    member.save()
    
    AuditLog.log(request.params["user"]["staff_id"], "add_member", {
        "member_id": member.id,
        "name": member.name,
        "email": member.email
    })
    
    return response.json({"message": "Member registered successfully.", "member": member.to_dict()}, 201)

@middleware(StaffAuthMiddleware)
@put("/api/members/{id:int}")
@tags("Staff Management")
@description("Edit a library member", "Modify member profile. Staff authentication required.")
async def edit_member(id, request, response):
    if "user" not in request.params:
        request, response = StaffAuthMiddleware.before_auth(request, response)
        if response.status_code >= 400:
            return response
    member = Member.find_by_id(id)
    if not member:
        return response.json({"error": "Member not found."}, 404)
        
    body = request.body
    if not body:
        return response.json({"error": "Request body required."}, 400)
        
    if body.get("email"):
        email = body["email"].strip().lower()
        if not validate_email(email):
            return response.json({"error": "Invalid email format."}, 400)
            
        # Check uniqueness if email is changing
        if email != member.email:
            existing = Member.where("email = ?", [email])
            if existing:
                return response.json({"error": "Email is already registered to another member."}, 400)
            member.email = email
            
    if body.get("name"):
        member.name = body["name"].strip()
        
    member.save()
    
    AuditLog.log(request.params["user"]["staff_id"], "edit_member", {
        "member_id": member.id,
        "name": member.name
    })
    
    return response.json({"message": "Member updated successfully.", "member": member.to_dict()})

@middleware(StaffAuthMiddleware)
@delete("/api/members/{id:int}")
@tags("Staff Management")
@description("Delete a member", "Remove member registration. Staff authentication required.")
async def delete_member(id, request, response):
    if "user" not in request.params:
        request, response = StaffAuthMiddleware.before_auth(request, response)
        if response.status_code >= 400:
            return response
    member = Member.find_by_id(id)
    if not member:
        return response.json({"error": "Member not found."}, 404)
        
    # Check for active loans
    active_loans = Loan.where("member_id = ? AND returned = 0", [id])
    if len(active_loans) > 0:
        return response.json({"error": "Cannot delete member. Member has active unreturned loans."}, 400)
        
    member.delete()
    
    AuditLog.log(request.params["user"]["staff_id"], "delete_member", {
        "member_id": id,
        "name": member.name
    })
    
    return response.json({"message": "Member deleted successfully."})

# ----------------- BORROW & RETURN -----------------

@middleware(StaffAuthMiddleware)
@post("/api/loans")
@tags("Staff Management")
@description("Record a book loan", "Check out a book to a member. Instantly returns receipt task to queue. Staff authentication required.")
@example({"book_id": 1, "member_id": 1})
async def record_loan(request, response):
    if "user" not in request.params:
        request, response = StaffAuthMiddleware.before_auth(request, response)
        if response.status_code >= 400:
            return response
    body = request.body
    if not body or not body.get("book_id") or not body.get("member_id"):
        return response.json({"error": "Book ID and Member ID are required."}, 400)
        
    book = Book.find_by_id(body["book_id"])
    if not book:
        return response.json({"error": "Book not found."}, 404)
        
    member = Member.find_by_id(body["member_id"])
    if not member:
        return response.json({"error": "Member not found."}, 404)
        
    # Verify availability
    if not book.is_available():
        return response.json({"error": "This book is already out on loan."}, 400)
        
    # Record the loan
    loan = Loan()
    loan.book_id = book.id
    loan.member_id = member.id
    loan.borrow_date = datetime.date.today().strftime("%Y-%m-%d")
    
    # Due in 14 days
    due = datetime.date.today() + datetime.timedelta(days=14)
    loan.due_date = due.strftime("%Y-%m-%d")
    loan.returned = 0
    loan.save()
    
    # 1. Enqueue asynchronous email receipt task (returns immediately)
    try:
        queue = Queue(topic="emails")
        queue.push({
            "to": member.email,
            "subject": f"Library Receipt: Borrowed '{book.title}'",
            "title": book.title,
            "due_date": loan.due_date,
            "body": f"Dear {member.name},\n\nThis is a receipt for borrowing '{book.title}' by {book.author}.\n\nBorrow Date: {loan.borrow_date}\nDue Date: {loan.due_date}\n\nPlease ensure the book is returned by the due date.\n\nHappy Reading!\nLend Community Library"
        })
    except Exception as e:
        # Don't fail the request if queue push fails, just log it
        print(f"Failed to push email receipt task to queue: {e}")
        
    # 2. Log staff audit trail
    AuditLog.log(request.params["user"]["staff_id"], "borrow_book", {
        "loan_id": loan.id,
        "book_id": book.id,
        "book_title": book.title,
        "member_id": member.id,
        "member_name": member.name
    })
    
    return response.json({
        "message": "Loan recorded successfully.",
        "loan": loan.to_dict()
    }, 201)

@middleware(StaffAuthMiddleware)
@post("/api/loans/return")
@tags("Staff Management")
@description("Record a book return", "Return a borrowed book. Staff authentication required.")
@example({"book_id": 1})
async def record_return(request, response):
    if "user" not in request.params:
        request, response = StaffAuthMiddleware.before_auth(request, response)
        if response.status_code >= 400:
            return response
    body = request.body
    if not body or not body.get("book_id"):
        return response.json({"error": "Book ID is required."}, 400)
        
    book = Book.find_by_id(body["book_id"])
    if not book:
        return response.json({"error": "Book not found."}, 404)
        
    # Find active loan
    loans = Loan.where("book_id = ? AND returned = 0", [book.id])
    if not loans:
        return response.json({"error": "No active loan found for this book."}, 400)
        
    loan = loans[0]
    loan.returned = 1
    loan.return_date = datetime.date.today().strftime("%Y-%m-%d")
    loan.save()
    
    member = Member.find_by_id(loan.member_id)
    member_name = member.name if member else "Unknown"
    
    # Log staff audit trail
    AuditLog.log(request.params["user"]["staff_id"], "return_book", {
        "loan_id": loan.id,
        "book_id": book.id,
        "book_title": book.title,
        "member_id": loan.member_id,
        "member_name": member_name
    })
    
    return response.json({
        "message": "Book returned successfully.",
        "loan": loan.to_dict()
    })

# ----------------- AUDIT LOGS -----------------

@middleware(StaffAuthMiddleware)
@get("/api/audit-logs")
@tags("Staff Management")
@description("Retrieve audit logs", "Get a list of all logged staff actions. Staff authentication required.")
async def list_audit_logs(request, response):
    if not hasattr(request, "user") or not request.user:
        request, response = StaffAuthMiddleware.before_auth(request, response)
        if response.status_code >= 400:
            return response
    logs = AuditLog.all()
    
    log_list = []
    if logs and hasattr(logs, "records"):
        recs = logs.records
    elif isinstance(logs, list):
        recs = logs
    else:
        recs = []
        
    for r in recs:
        # Load staff name
        staff_name = "Unknown"
        s_id = r.get("staff_id") if isinstance(r, dict) else getattr(r, "staff_id", None)
        if s_id:
            from src.orm.staff import Staff
            staff = Staff.find_by_id(s_id)
            if staff:
                staff_name = staff.name
                
        r_dict = r.to_dict() if hasattr(r, "to_dict") else dict(r)
        r_dict["staff_name"] = staff_name
        log_list.append(r_dict)
        
    # Sort chronologically descending (newest first)
    log_list.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return response.json(log_list)
