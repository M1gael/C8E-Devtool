import datetime
import json
import math
from tina4_python.core.router import get, post, noauth
from tina4_python.auth import Auth
from src.orm.Staff import Staff
from src.orm.Book import Book
from src.orm.Member import Member
from src.orm.Loan import Loan
from src.orm.AuditLog import AuditLog
from src.app.auth import get_authenticated_staff
from src.app.template import render
from tina4_python.queue import Queue

def log_change_web(staff_id, action, details):
    """Utility to record change in audit logs from web route."""
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
        print(f"[WEB ERROR] Failed to write audit log: {e}")

# 1. Homepage: Book Catalogue (Public GET)
@get("/")
async def web_home(request, response):
    limit = 6  # 6 books per page for nice visual grid
    offset = int(request.params.get("offset", 0))
    search = request.params.get("search", "").strip()

    conditions = "1=1"
    params = []
    if search:
        conditions += " AND (title LIKE ? OR author LIKE ? OR published_year LIKE ?)"
        search_param = f"%{search}%"
        params.extend([search_param, search_param, search_param])

    books = Book.where(conditions, params, limit=limit, offset=offset)
    total_count = Book.count(conditions, params)
    pages = math.ceil(total_count / limit) if total_count > 0 else 1

    pagination = {
        "total": total_count,
        "limit": limit,
        "offset": offset,
        "pages": pages,
        "prev_offset": max(0, offset - limit),
        "next_offset": offset + limit
    }

    return response(render("catalogue.twig", {
        "books": [b.to_dict() for b in books],
        "search": search,
        "pagination": pagination
    }, request))

# 2. Book Detail Page (Public GET)
@get("/book/{id}")
async def web_book_detail(request, response):
    book_id = request.params.get("id")
    book = Book()
    if not book.load("id = ?", [book_id]):
        return response("Book Not Found", 404)

    # Fetch loan history
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

    # Availability check
    active_loans = Loan.count("book_id = ? AND returned = 0", [book.id])
    is_available = 1 if active_loans == 0 else 0

    book_data = book.to_dict()
    book_data["is_available"] = is_available
    book_data["history"] = history

    return response(render("book.twig", {
        "book": book_data
    }, request))

# 3. Login Page (Public GET)
@get("/login")
async def web_login_page(request, response):
    # If already logged in, redirect to admin
    if hasattr(request, "session") and request.session.get("staff_id"):
        return response.redirect("/admin")
    return response(render("login.twig", {}, request))

# 4. Login Submission (Public POST)
@noauth()
@post("/login")
async def web_login_submit(request, response):
    email = request.body.get("email", "").strip()
    password = request.body.get("password", "")

    if not email or not password:
        return response(render("login.twig", {"error": "Email and password are required"}, request))

    staff = Staff()
    if staff.load("email = ?", [email]) and Auth.check_password(password, staff.password_hash):
        if hasattr(request, "session") and request.session:
            request.session.set("staff_id", staff.id)
            request.session.set("staff_name", staff.name)
        return response.redirect("/admin")

    return response(render("login.twig", {"error": "Invalid email or password"}, request))

# 5. Logout Handler (Public GET)
@get("/logout")
async def web_logout(request, response):
    if hasattr(request, "session") and request.session:
        request.session.set("staff_id", None)
        request.session.set("staff_name", None)
    return response.redirect("/?lang=" + (request.session.get("lang") or "en"))

# 6. Admin Overview Dashboard (Staff GET)
@get("/admin")
async def web_admin_dashboard(request, response):
    staff = get_authenticated_staff(request)
    if not staff:
        return response.redirect("/login")

    # Fetch stats
    total_books = Book.count()
    total_members = Member.count()
    active_loans_count = Loan.count("returned = 0")
    returned_loans_count = Loan.count("returned = 1")

    # Fetch active loans for listing
    loans = Loan.where("returned = 0", limit=50)
    active_loans_list = []
    for l in loans:
        book = Book()
        book.load("id = ?", [l.book_id])
        member = Member()
        member.load("id = ?", [l.member_id])
        active_loans_list.append({
            "id": l.id,
            "borrow_date": l.borrow_date,
            "due_date": l.due_date,
            "book": book.to_dict() if hasattr(book, "title") else {},
            "member": member.to_dict() if hasattr(member, "name") else {}
        })

    # Flash messages
    success = request.params.get("success", "")
    error = request.params.get("error", "")

    return response(render("admin/dashboard.twig", {
        "stats": {
            "books": total_books,
            "members": total_members,
            "active_loans": active_loans_count,
            "returned_loans": returned_loans_count
        },
        "active_loans": active_loans_list,
        "success": success,
        "error": error
    }, request))

# 7. Admin Manage Books (Staff GET)
@get("/admin/books")
async def web_admin_books(request, response):
    staff = get_authenticated_staff(request)
    if not staff:
        return response.redirect("/login")

    edit_id = request.params.get("edit_id")
    edit_book = None
    if edit_id:
        book = Book()
        if book.load("id = ?", [edit_id]):
            edit_book = book.to_dict()

    books = Book.all(limit=100)
    success = request.params.get("success", "")
    error = request.params.get("error", "")

    return response(render("admin/books.twig", {
        "books": [b.to_dict() for b in books],
        "edit_book": edit_book,
        "success": success,
        "error": error
    }, request))

# 8. Add Book (Staff POST)
@noauth()
@post("/admin/books/add")
async def web_admin_add_book(request, response):
    staff = get_authenticated_staff(request)
    if not staff:
        return response.redirect("/login")

    title = request.body.get("title", "").strip()
    author = request.body.get("author", "").strip()
    published_year = request.body.get("published_year")
    isbn = request.body.get("isbn", "").strip()
    cover_image = request.body.get("cover_image", "").strip()

    if not title or not author or not published_year or not isbn:
        return response.redirect("/admin/books?error=All fields are required")

    try:
        published_year = int(published_year)
    except ValueError:
        return response.redirect("/admin/books?error=Published year must be a valid number")

    book = Book(
        title=title,
        author=author,
        published_year=published_year,
        isbn=isbn,
        cover_image=cover_image or "/images/default-cover.png",
        is_available=1
    )
    book.save()

    log_change_web(staff.id, "ADD_BOOK", {"book_id": book.id, "title": title})

    return response.redirect("/admin/books?success=Book added successfully")

# 9. Edit Book (Staff POST)
@noauth()
@post("/admin/books/edit/{id}")
async def web_admin_edit_book(request, response):
    staff = get_authenticated_staff(request)
    if not staff:
        return response.redirect("/login")

    book_id = request.params.get("id")
    book = Book()
    if not book.load("id = ?", [book_id]):
        return response.redirect("/admin/books?error=Book not found")

    title = request.body.get("title", "").strip()
    author = request.body.get("author", "").strip()
    published_year = request.body.get("published_year")
    isbn = request.body.get("isbn", "").strip()
    cover_image = request.body.get("cover_image", "").strip()

    if not title or not author or not published_year or not isbn:
        return response.redirect(f"/admin/books?edit_id={book_id}&error=All fields are required")

    try:
        published_year = int(published_year)
    except ValueError:
        return response.redirect(f"/admin/books?edit_id={book_id}&error=Published year must be a valid number")

    book.title = title
    book.author = author
    book.published_year = published_year
    book.isbn = isbn
    if cover_image:
        book.cover_image = cover_image
    book.save()

    log_change_web(staff.id, "EDIT_BOOK", {"book_id": book.id, "title": title})

    return response.redirect("/admin/books?success=Book updated successfully")

# 10. Delete Book (Staff POST)
@noauth()
@post("/admin/books/delete")
async def web_admin_delete_book(request, response):
    staff = get_authenticated_staff(request)
    if not staff:
        return response.redirect("/login")

    book_id = request.body.get("book_id")
    book = Book()
    if not book.load("id = ?", [book_id]):
        return response.redirect("/admin/books?error=Book not found")

    # Check if has active loans
    active_loans = Loan.count("book_id = ? AND returned = 0", [book_id])
    if active_loans > 0:
        return response.redirect("/admin/books?error=Cannot delete book that is currently borrowed")

    log_change_web(staff.id, "DELETE_BOOK", {"book_id": book.id, "title": book.title})
    book.delete()

    return response.redirect("/admin/books?success=Book deleted successfully")

# 11. Admin Manage Members (Staff GET)
@get("/admin/members")
async def web_admin_members(request, response):
    staff = get_authenticated_staff(request)
    if not staff:
        return response.redirect("/login")

    edit_id = request.params.get("edit_id")
    edit_member = None
    if edit_id:
        member = Member()
        if member.load("id = ?", [edit_id]):
            edit_member = member.to_dict()

    members = Member.all(limit=100)
    success = request.params.get("success", "")
    error = request.params.get("error", "")

    return response(render("admin/members.twig", {
        "members": [m.to_dict() for m in members],
        "edit_member": edit_member,
        "success": success,
        "error": error
    }, request))

# 12. Add Member (Staff POST)
@noauth()
@post("/admin/members/add")
async def web_admin_add_member(request, response):
    staff = get_authenticated_staff(request)
    if not staff:
        return response.redirect("/login")

    name = request.body.get("name", "").strip()
    email = request.body.get("email", "").strip()

    if not name or not email:
        return response.redirect("/admin/members?error=All fields are required")

    # Check duplicate
    duplicate = Member()
    if duplicate.load("email = ?", [email]):
        return response.redirect("/admin/members?error=Email address is already registered")

    member = Member(
        name=name,
        email=email,
        join_date=datetime.date.today().isoformat()
    )
    member.save()

    log_change_web(staff.id, "ADD_MEMBER", {"member_id": member.id, "name": name, "email": email})

    return response.redirect("/admin/members?success=Member registered successfully")

# 13. Edit Member (Staff POST)
@noauth()
@post("/admin/members/edit/{id}")
async def web_admin_edit_member(request, response):
    staff = get_authenticated_staff(request)
    if not staff:
        return response.redirect("/login")

    member_id = request.params.get("id")
    member = Member()
    if not member.load("id = ?", [member_id]):
        return response.redirect("/admin/members?error=Member not found")

    name = request.body.get("name", "").strip()
    email = request.body.get("email", "").strip()

    if not name or not email:
        return response.redirect(f"/admin/members?edit_id={member_id}&error=All fields are required")

    # Check unique email
    duplicate = Member()
    if duplicate.load("email = ? AND id != ?", [email, member_id]):
        return response.redirect(f"/admin/members?edit_id={member_id}&error=Email is registered by another member")

    member.name = name
    member.email = email
    member.save()

    log_change_web(staff.id, "EDIT_MEMBER", {"member_id": member.id, "name": name})

    return response.redirect("/admin/members?success=Member updated successfully")

# 14. Delete Member (Staff POST)
@noauth()
@post("/admin/members/delete")
async def web_admin_delete_member(request, response):
    staff = get_authenticated_staff(request)
    if not staff:
        return response.redirect("/login")

    member_id = request.body.get("member_id")
    member = Member()
    if not member.load("id = ?", [member_id]):
        return response.redirect("/admin/members?error=Member not found")

    # Check if has active loans
    active_loans = Loan.count("member_id = ? AND returned = 0", [member_id])
    if active_loans > 0:
        return response.redirect("/admin/members?error=Cannot delete member with active loans")

    log_change_web(staff.id, "DELETE_MEMBER", {"member_id": member.id, "name": member.name})
    member.delete()

    return response.redirect("/admin/members?success=Member deleted successfully")

# 15. Admin Manage Loans (Staff GET)
@get("/admin/loans")
async def web_admin_loans(request, response):
    staff = get_authenticated_staff(request)
    if not staff:
        return response.redirect("/login")

    selected_book_id = request.params.get("book_id")
    if selected_book_id:
        try:
            selected_book_id = int(selected_book_id)
        except ValueError:
            selected_book_id = None

    # Get available books only
    available_books = Book.where("is_available = 1", limit=100)
    members = Member.all(limit=100)

    # Get all active loans
    loans = Loan.where("returned = 0", limit=100)
    active_loans_list = []
    for l in loans:
        book = Book()
        book.load("id = ?", [l.book_id])
        member = Member()
        member.load("id = ?", [l.member_id])
        active_loans_list.append({
            "id": l.id,
            "borrow_date": l.borrow_date,
            "due_date": l.due_date,
            "book": book.to_dict() if hasattr(book, "title") else {},
            "member": member.to_dict() if hasattr(member, "name") else {}
        })

    success = request.params.get("success", "")
    error = request.params.get("error", "")

    return response(render("admin/loans.twig", {
        "available_books": [b.to_dict() for b in available_books],
        "members": [m.to_dict() for m in members],
        "active_loans": active_loans_list,
        "selected_book_id": selected_book_id,
        "success": success,
        "error": error
    }, request))

# 16. Record Loan Submission (Staff POST)
@noauth()
@post("/admin/loans/add")
async def web_admin_add_loan(request, response):
    staff = get_authenticated_staff(request)
    if not staff:
        return response.redirect("/login")

    book_id = request.body.get("book_id")
    member_id = request.body.get("member_id")
    due_date = request.body.get("due_date", "").strip()

    if not book_id or not member_id or not due_date:
        return response.redirect("/admin/loans?error=All fields are required")

    # Load Book
    book = Book()
    if not book.load("id = ?", [book_id]):
        return response.redirect("/admin/loans?error=Book not found")

    # Load Member
    member = Member()
    if not member.load("id = ?", [member_id]):
        return response.redirect("/admin/loans?error=Member not found")

    # Double check availability
    active_loans = Loan.count("book_id = ? AND returned = 0", [book_id])
    if active_loans > 0 or book.is_available == 0:
        return response.redirect("/admin/loans?error=This book is already out on loan")

    # Record loan
    borrow_date = datetime.date.today().isoformat()
    loan = Loan(
        book_id=book_id,
        member_id=member_id,
        borrow_date=borrow_date,
        due_date=due_date,
        returned=0
    )
    loan.save()

    # Update book status
    book.is_available = 0
    book.save()

    # Enqueue receipt email
    try:
        queue = Queue(topic="loan_emails")
        queue.push({
            "to": member.email,
            "subject": f"Library Receipt: Borrowed '{book.title}'",
            "body": f"""
            <h2>Lend Community Library</h2>
            <p>Dear {member.name},</p>
            <p>You have borrowed <strong>{book.title}</strong> by {book.author}.</p>
            <p><strong>Borrow Date:</strong> {borrow_date}</p>
            <p><strong>Due Date:</strong> {due_date}</p>
            <br>
            <p>Thank you!</p>
            """
        })
        print(f"[WEB] Enqueued loan receipt email to {member.email}")
    except Exception as qe:
        print(f"[WEB ERROR] Failed to enqueue receipt email: {qe}")

    log_change_web(staff.id, "RECORD_LOAN", {
        "loan_id": loan.id,
        "book_id": book.id,
        "book_title": book.title,
        "member_id": member.id,
        "member_name": member.name
    })

    return response.redirect("/admin/loans?success=Loan recorded successfully")

# 17. Return Book (Staff POST)
@noauth()
@post("/admin/loans/return")
async def web_admin_return_loan(request, response):
    staff = get_authenticated_staff(request)
    if not staff:
        return response.redirect("/login")

    loan_id = request.body.get("loan_id")
    loan = Loan()
    if not loan.load("id = ?", [loan_id]):
        return response.redirect("/admin?error=Loan not found")

    if loan.returned == 1:
        return response.redirect("/admin?error=Book already returned")

    loan.returned = 1
    loan.save()

    # Mark book available
    book = Book()
    if book.load("id = ?", [loan.book_id]):
        book.is_available = 1
        book.save()

    log_change_web(staff.id, "RECORD_RETURN", {
        "loan_id": loan.id,
        "book_id": loan.book_id,
        "book_title": book.title if hasattr(book, "title") else ""
    })

    # Redirect to referrer or admin
    ref = request.headers.get("referer", "/admin")
    if "/admin/loans" in ref:
        return response.redirect("/admin/loans?success=Book returned successfully")
    return response.redirect("/admin?success=Book returned successfully")

# 18. Audit Logs Viewer (Staff GET)
@get("/admin/logs")
async def web_admin_logs(request, response):
    staff = get_authenticated_staff(request)
    if not staff:
        return response.redirect("/login")

    logs = AuditLog.all()
    logs_sorted = sorted(logs, key=lambda l: l.id, reverse=True)
    
    logs_view = []
    for l in logs_sorted:
        s = Staff()
        s.load("id = ?", [l.staff_id])
        logs_view.append({
            "id": l.id,
            "staff_id": l.staff_id,
            "staff_name": s.name if hasattr(s, "name") else "Unknown",
            "action": l.action,
            "details": json.loads(l.details) if l.details else {},
            "created_at": l.created_at
        })

    return response(render("admin/logs.twig", {
        "logs": logs_view
    }, request))
