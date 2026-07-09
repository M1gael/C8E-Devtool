import datetime
import json
from tina4_python.core.router import get, post, put, delete, noauth
from tina4_python.auth import get_token, Auth
from src.orm.Staff import Staff
from src.orm.Book import Book
from src.orm.Member import Member
from src.orm.Loan import Loan
from src.orm.AuditLog import AuditLog
from src.app.auth import get_authenticated_staff
from tina4_python.queue import Queue

def log_change(staff_id, action, details):
    """Utility to record change in audit logs."""
    try:
        now = datetime.datetime.now().isoformat()
        log = AuditLog(
            staff_id=staff_id,
            action=action,
            details=json.dumps(details),
            created_at=now
        )
        log.save()
    except Exception as e:
        print(f"[API ERROR] Failed to write audit log: {e}")

# 1. Staff Login (Public POST)
@noauth()
@post("/api/staff/login")
async def api_staff_login(request, response):
    email = request.body.get("email", "").strip()
    password = request.body.get("password", "")

    if not email or not password:
        return response({"error": "Email and password are required"}, 400)

    staff = Staff()
    if staff.load("email = ?", [email]):
        if Auth.check_password(password, staff.password_hash):
            token = get_token({"staff_id": staff.id}, expires_in=60)
            # Store in session for web interface
            if hasattr(request, "session") and request.session:
                request.session.set("staff_id", staff.id)
                request.session.set("staff_name", staff.name)
            return response({"token": token, "staff": {"id": staff.id, "name": staff.name, "email": staff.email}})

    return response({"error": "Invalid email or password"}, 401)

# 2. List & Search Books (Public GET)
@get("/api/books")
async def api_list_books(request, response):
    # Parse query parameters
    limit = int(request.params.get("limit", 10))
    offset = int(request.params.get("offset", 0))
    search = request.params.get("search", "").strip()

    # Build SQL condition
    conditions = "1=1"
    params = []
    if search:
        conditions += " AND (title LIKE ? OR author LIKE ? OR published_year LIKE ?)"
        search_param = f"%{search}%"
        params.extend([search_param, search_param, search_param])

    books = Book.where(conditions, params, limit=limit, offset=offset)
    total_count = Book.count(conditions, params)

    return response({
        "books": [b.to_dict() for b in books],
        "pagination": {
            "total": total_count,
            "limit": limit,
            "offset": offset
        }
    })

# 3. Create Book (Staff POST)
@noauth()
@post("/api/books")
async def api_create_book(request, response):
    staff = get_authenticated_staff(request)
    if not staff:
        return response({"error": "Unauthorized"}, 401)

    title = request.body.get("title", "").strip()
    author = request.body.get("author", "").strip()
    published_year = request.body.get("published_year")
    isbn = request.body.get("isbn", "").strip()
    cover_image = request.body.get("cover_image", "").strip()

    # Validation
    if not title or not author or not published_year or not isbn:
        return response({"error": "Title, author, published year, and ISBN are required"}, 400)

    try:
        published_year = int(published_year)
    except ValueError:
        return response({"error": "Published year must be a valid integer"}, 400)

    book = Book(
        title=title,
        author=author,
        published_year=published_year,
        isbn=isbn,
        cover_image=cover_image or "/images/default-cover.png",
        is_available=1
    )
    book.save()

    log_change(staff.id, "ADD_BOOK", {"book_id": book.id, "title": title})

    return response(book.to_dict(), 201)

# 4. Book Detail (Public GET)
@get("/api/books/{id}")
async def api_book_detail(request, response):
    book_id = request.params.get("id")
    book = Book()
    if not book.load("id = ?", [book_id]):
        return response({"error": "Book not found"}, 404)

    # Get borrowing history
    loans = Loan.where("book_id = ?", [book.id])
    history = []
    for l in loans:
        member = Member()
        member.load("id = ?", [l.member_id])
        history.append({
            "id": l.id,
            "borrow_date": l.borrow_date,
            "due_date": l.due_date,
            "returned": l.returned,
            "member": {
                "id": member.id,
                "name": member.name,
                "email": member.email
            }
        })

    # Availability dynamic check
    active_loans_count = Loan.count("book_id = ? AND returned = 0", [book.id])
    is_available = 1 if active_loans_count == 0 else 0

    # Sync DB availability field just in case
    if book.is_available != is_available:
        book.is_available = is_available
        book.save()

    data = book.to_dict()
    data["is_available"] = is_available
    data["history"] = history

    return response(data)

# 5. Update Book (Staff PUT)
@noauth()
@put("/api/books/{id}")
async def api_update_book(request, response):
    staff = get_authenticated_staff(request)
    if not staff:
        return response({"error": "Unauthorized"}, 401)

    book_id = request.params.get("id")
    book = Book()
    if not book.load("id = ?", [book_id]):
        return response({"error": "Book not found"}, 404)

    title = request.body.get("title", "").strip()
    author = request.body.get("author", "").strip()
    published_year = request.body.get("published_year")
    isbn = request.body.get("isbn", "").strip()
    cover_image = request.body.get("cover_image", "").strip()

    if not title or not author or not published_year or not isbn:
        return response({"error": "Title, author, published year, and ISBN are required"}, 400)

    try:
        published_year = int(published_year)
    except ValueError:
        return response({"error": "Published year must be a valid integer"}, 400)

    book.title = title
    book.author = author
    book.published_year = published_year
    book.isbn = isbn
    if cover_image:
        book.cover_image = cover_image
    book.save()

    log_change(staff.id, "EDIT_BOOK", {"book_id": book.id, "title": title})

    return response(book.to_dict())

# 6. Delete Book (Staff DELETE)
@noauth()
@delete("/api/books/{id}")
async def api_delete_book(request, response):
    staff = get_authenticated_staff(request)
    if not staff:
        return response({"error": "Unauthorized"}, 401)

    book_id = request.params.get("id")
    book = Book()
    if not book.load("id = ?", [book_id]):
        return response({"error": "Book not found"}, 404)

    # Check if there are active loans
    active_loans = Loan.count("book_id = ? AND returned = 0", [book_id])
    if active_loans > 0:
        return response({"error": "Cannot delete book with active loans"}, 400)

    log_change(staff.id, "DELETE_BOOK", {"book_id": book.id, "title": book.title})
    book.delete()

    return response({"message": "Book deleted successfully"})

# 7. List Members (Staff GET)
@noauth()
@get("/api/members")
async def api_list_members(request, response):
    staff = get_authenticated_staff(request)
    if not staff:
        return response({"error": "Unauthorized"}, 401)

    members = Member.all()
    return response([m.to_dict() for m in members])

# 8. Create Member (Staff POST)
@noauth()
@post("/api/members")
async def api_create_member(request, response):
    staff = get_authenticated_staff(request)
    if not staff:
        return response({"error": "Unauthorized"}, 401)

    name = request.body.get("name", "").strip()
    email = request.body.get("email", "").strip()

    if not name or not email:
        return response({"error": "Name and email are required"}, 400)

    # Check duplicate email
    duplicate = Member()
    if duplicate.load("email = ?", [email]):
        return response({"error": "Email is already registered"}, 400)

    now_date = datetime.date.today().isoformat()
    member = Member(
        name=name,
        email=email,
        join_date=now_date
    )
    member.save()

    log_change(staff.id, "ADD_MEMBER", {"member_id": member.id, "name": name, "email": email})

    return response(member.to_dict(), 201)

# 9. Update Member (Staff PUT)
@noauth()
@put("/api/members/{id}")
async def api_update_member(request, response):
    staff = get_authenticated_staff(request)
    if not staff:
        return response({"error": "Unauthorized"}, 401)

    member_id = request.params.get("id")
    member = Member()
    if not member.load("id = ?", [member_id]):
        return response({"error": "Member not found"}, 404)

    name = request.body.get("name", "").strip()
    email = request.body.get("email", "").strip()

    if not name or not email:
        return response({"error": "Name and email are required"}, 400)

    # Check email uniqueness
    duplicate = Member()
    if duplicate.load("email = ? AND id != ?", [email, member_id]):
        return response({"error": "Email is already registered by another member"}, 400)

    member.name = name
    member.email = email
    member.save()

    log_change(staff.id, "EDIT_MEMBER", {"member_id": member.id, "name": name})

    return response(member.to_dict())

# 10. Delete Member (Staff DELETE)
@noauth()
@delete("/api/members/{id}")
async def api_delete_member(request, response):
    staff = get_authenticated_staff(request)
    if not staff:
        return response({"error": "Unauthorized"}, 401)

    member_id = request.params.get("id")
    member = Member()
    if not member.load("id = ?", [member_id]):
        return response({"error": "Member not found"}, 404)

    # Check if there are active loans
    active_loans = Loan.count("member_id = ? AND returned = 0", [member_id])
    if active_loans > 0:
        return response({"error": "Cannot delete member with active loans"}, 400)

    log_change(staff.id, "DELETE_MEMBER", {"member_id": member.id, "name": member.name})
    member.delete()

    return response({"message": "Member deleted successfully"})

# 11. Record Loan (Staff POST)
@noauth()
@post("/api/loans")
async def api_create_loan(request, response):
    staff = get_authenticated_staff(request)
    if not staff:
        return response({"error": "Unauthorized"}, 401)

    book_id = request.body.get("book_id")
    member_id = request.body.get("member_id")
    due_date = request.body.get("due_date", "").strip()

    if not book_id or not member_id or not due_date:
        return response({"error": "Book ID, Member ID, and Due Date are required"}, 400)

    # Verify Book
    book = Book()
    if not book.load("id = ?", [book_id]):
        return response({"error": "Book not found"}, 404)

    # Verify Member
    member = Member()
    if not member.load("id = ?", [member_id]):
        return response({"error": "Member not found"}, 404)

    # Check if Book is currently borrowed
    active_loans = Loan.count("book_id = ? AND returned = 0", [book_id])
    if active_loans > 0 or book.is_available == 0:
        return response({"error": "Book is already out on loan"}, 400)

    # Record the loan
    borrow_date = datetime.date.today().isoformat()
    loan = Loan(
        book_id=book_id,
        member_id=member_id,
        borrow_date=borrow_date,
        due_date=due_date,
        returned=0
    )
    loan.save()

    # Update book availability
    book.is_available = 0
    book.save()

    # Push to background email queue immediately
    try:
        queue = Queue(topic="loan_emails")
        queue.push({
            "to": member.email,
            "subject": f"Library Receipt: Borrowed '{book.title}'",
            "body": f"""
            <h2>Lend Community Library</h2>
            <p>Dear {member.name},</p>
            <p>You have successfully borrowed <strong>{book.title}</strong> by {book.author}.</p>
            <p><strong>Borrow Date:</strong> {borrow_date}</p>
            <p><strong>Due Date:</strong> {due_date}</p>
            <p>Please return the book by the due date.</p>
            <br>
            <p>Thank you!</p>
            """
        })
        print(f"[API] Enqueued loan receipt email to {member.email}")
    except Exception as qe:
        print(f"[API ERROR] Failed to enqueue receipt email: {qe}")

    log_change(staff.id, "RECORD_LOAN", {
        "loan_id": loan.id,
        "book_id": book.id,
        "book_title": book.title,
        "member_id": member.id,
        "member_name": member.name
    })

    return response(loan.to_dict(), 201)

# 12. Record Return (Staff POST)
@noauth()
@post("/api/loans/return")
async def api_record_return(request, response):
    staff = get_authenticated_staff(request)
    if not staff:
        return response({"error": "Unauthorized"}, 401)

    book_id = request.body.get("book_id")
    loan_id = request.body.get("loan_id")

    if not book_id and not loan_id:
        return response({"error": "Either Book ID or Loan ID is required"}, 400)

    loan = Loan()
    if loan_id:
        if not loan.load("id = ?", [loan_id]):
            return response({"error": "Loan not found"}, 404)
    else:
        # Load the active loan for the book
        if not loan.load("book_id = ? AND returned = 0", [book_id]):
            return response({"error": "No active loan found for this book"}, 404)

    # Check if already returned
    if loan.returned == 1:
        return response({"error": "This loan is already returned"}, 400)

    # Mark as returned
    loan.returned = 1
    loan.save()

    # Mark book as available
    book = Book()
    if book.load("id = ?", [loan.book_id]):
        book.is_available = 1
        book.save()

    log_change(staff.id, "RECORD_RETURN", {
        "loan_id": loan.id,
        "book_id": loan.book_id,
        "book_title": book.title if hasattr(book, "title") else ""
    })

    return response({"message": "Book returned successfully", "loan": loan.to_dict()})

# 13. Get Audit Logs (Staff GET)
@noauth()
@get("/api/staff/logs")
async def api_get_logs(request, response):
    staff = get_authenticated_staff(request)
    if not staff:
        return response({"error": "Unauthorized"}, 401)

    logs = AuditLog.all()
    # Sort logs by id descending for latest first
    logs_sorted = sorted(logs, key=lambda l: l.id, reverse=True)
    
    result = []
    for l in logs_sorted:
        s = Staff()
        s.load("id = ?", [l.staff_id])
        result.append({
            "id": l.id,
            "staff_id": l.staff_id,
            "staff_name": s.name if hasattr(s, "name") else "Unknown",
            "action": l.action,
            "details": json.loads(l.details) if l.details else {},
            "created_at": l.created_at
        })
    return response(result)
