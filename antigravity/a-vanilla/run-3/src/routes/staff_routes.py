import json
from datetime import datetime, date
from tina4_python.core.router import get, post, put, delete, secured
from tina4_python.database import Database
from tina4_python.queue import Queue
from src.app.utils import render_template, get_current_user
from src.app.audit import log_change
from src.orm.Book import Book
from src.orm.Member import Member
from src.orm.Loan import Loan

# ==========================================
# Web Views for Staff Area (Manually Secured)
# ==========================================

@get("/staff/dashboard")
async def staff_dashboard(request, response):
    """Renders the staff dashboard with overall library statistics."""
    current_user = get_current_user(request)
    if not current_user:
        return response.redirect("/login")
        
    db = Database()
    
    # Calculate stats
    total_books_row = db.fetch_one("SELECT COUNT(*) as total FROM books")
    total_books = total_books_row.get("total", 0) if total_books_row else 0
    
    total_members_row = db.fetch_one("SELECT COUNT(*) as total FROM members")
    total_members = total_members_row.get("total", 0) if total_members_row else 0
    
    active_loans_row = db.fetch_one("SELECT COUNT(*) as total FROM loans WHERE returned = 0")
    active_loans = active_loans_row.get("total", 0) if active_loans_row else 0
    
    returned_loans_row = db.fetch_one("SELECT COUNT(*) as total FROM loans WHERE returned = 1")
    returned_loans = returned_loans_row.get("total", 0) if returned_loans_row else 0
    
    return render_template(request, response, "staff/dashboard.twig", {
        "user": current_user,
        "total_books": total_books,
        "total_members": total_members,
        "active_loans": active_loans,
        "returned_loans": returned_loans
    })

@get("/staff/books")
async def staff_books(request, response):
    """Renders the staff books management page."""
    current_user = get_current_user(request)
    if not current_user:
        return response.redirect("/login")
        
    db = Database()
    # Simple list of books with availability
    sql = """
        SELECT b.*,
               CASE WHEN (SELECT COUNT(*) FROM loans l WHERE l.book_id = b.id AND l.returned = 0) > 0 THEN 0 ELSE 1 END as available
        FROM books b
        ORDER BY b.title ASC
    """
    result = db.fetch(sql)
    books = result.records if result else []
    
    return render_template(request, response, "staff/books.twig", {
        "user": current_user,
        "books": books
    })

@get("/staff/members")
async def staff_members(request, response):
    """Renders the staff members management page."""
    current_user = get_current_user(request)
    if not current_user:
        return response.redirect("/login")
        
    db = Database()
    result = db.fetch("SELECT * FROM members ORDER BY name ASC")
    members = result.records if result else []
    
    return render_template(request, response, "staff/members.twig", {
        "user": current_user,
        "members": members
    })

@get("/staff/loans")
async def staff_loans(request, response):
    """Renders the loans and returns management page."""
    current_user = get_current_user(request)
    if not current_user:
        return response.redirect("/login")
        
    db = Database()
    
    # Fetch books that are available for a new loan
    books_sql = """
        SELECT b.*
        FROM books b
        WHERE (SELECT COUNT(*) FROM loans l WHERE l.book_id = b.id AND l.returned = 0) = 0
        ORDER BY b.title ASC
    """
    books_result = db.fetch(books_sql)
    available_books = books_result.records if books_result else []
    
    # Fetch all members
    members_result = db.fetch("SELECT * FROM members ORDER BY name ASC")
    members = members_result.records if members_result else []
    
    # Fetch active loans to record returns
    active_loans_sql = """
        SELECT l.*, b.title as book_title, m.name as member_name, m.email as member_email
        FROM loans l
        JOIN books b ON l.book_id = b.id
        JOIN members m ON l.member_id = m.id
        WHERE l.returned = 0
        ORDER BY l.due_date ASC
    """
    loans_result = db.fetch(active_loans_sql)
    active_loans = loans_result.records if loans_result else []
    
    return render_template(request, response, "staff/loans.twig", {
        "user": current_user,
        "available_books": available_books,
        "members": members,
        "active_loans": active_loans,
        "default_due_date": date.today().isoformat()
    })

@get("/staff/audit-logs")
async def staff_audit_view(request, response):
    """Renders the audit trail log page."""
    current_user = get_current_user(request)
    if not current_user:
        return response.redirect("/login")
        
    db = Database()
    # Fetch audit logs joined with the staff user who made the change
    sql = """
        SELECT a.*, u.name as staff_name, u.email as staff_email
        FROM audit_logs a
        LEFT JOIN users u ON a.user_id = u.id
        ORDER BY a.created_at DESC
    """
    result = db.fetch(sql)
    logs = result.records if result else []
    
    return render_template(request, response, "staff/audit_logs.twig", {
        "user": current_user,
        "logs": logs
    })

# ==========================================
# REST API Endpoints (Writes Secured by Default, GETs decorated)
# ==========================================

# --- Books CRUD ---

@post("/api/books")
async def api_add_book(request, response):
    current_user = get_current_user(request)
    if not current_user:
        return response.json({"error": "Unauthorized"}, 401)
        
    body = request.body or {}
    title = body.get("title", "").strip()
    author = body.get("author", "").strip()
    published_year = body.get("published_year")
    isbn = body.get("isbn", "").strip()
    cover_image = body.get("cover_image", "").strip() or "default-cover.jpg"
    
    if not title or not author or not published_year or not isbn:
        return response.json({
            "error": "Bad Request",
            "message": "Title, Author, Published Year, and ISBN are required"
        }, 400)
        
    try:
        year = int(published_year)
    except (ValueError, TypeError):
        return response.json({
            "error": "Bad Request",
            "message": "Published Year must be a valid integer"
        }, 400)
        
    book = Book(
        title=title,
        author=author,
        published_year=year,
        isbn=isbn,
        cover_image=cover_image
    )
    book.save()
    
    log_change(current_user["id"], "ADD_BOOK", {"book_id": book.id, "title": title, "isbn": isbn})
    
    return response.json(book, 201)

@put("/api/books/{id:int}")
async def api_edit_book(id, request, response):
    current_user = get_current_user(request)
    if not current_user:
        return response.json({"error": "Unauthorized"}, 401)
        
    book = Book.find(id)
    if not book:
        return response.json({"error": "Not Found", "message": "Book not found"}, 404)
        
    body = request.body or {}
    title = body.get("title", "").strip()
    author = body.get("author", "").strip()
    published_year = body.get("published_year")
    isbn = body.get("isbn", "").strip()
    cover_image = body.get("cover_image", "").strip()
    
    if not title or not author or not published_year or not isbn:
        return response.json({
            "error": "Bad Request",
            "message": "Title, Author, Published Year, and ISBN are required"
        }, 400)
        
    try:
        year = int(published_year)
    except (ValueError, TypeError):
        return response.json({
            "error": "Bad Request",
            "message": "Published Year must be a valid integer"
        }, 400)
        
    # Update fields
    book.title = title
    book.author = author
    book.published_year = year
    book.isbn = isbn
    if cover_image:
        book.cover_image = cover_image
    book.save()
    
    log_change(current_user["id"], "EDIT_BOOK", {"book_id": id, "title": title, "isbn": isbn})
    
    return response.json(book)

@delete("/api/books/{id:int}")
async def api_delete_book(id, request, response):
    current_user = get_current_user(request)
    if not current_user:
        return response.json({"error": "Unauthorized"}, 401)
        
    book = Book.find(id)
    if not book:
        return response.json({"error": "Not Found", "message": "Book not found"}, 404)
        
    title = book.title
    book.delete()
    
    log_change(current_user["id"], "DELETE_BOOK", {"book_id": id, "title": title})
    
    return response.json({"message": "Book deleted successfully"})

# --- Members CRUD ---

@secured()
@get("/api/members")
async def api_list_members(request, response):
    db = Database()
    result = db.fetch("SELECT * FROM members ORDER BY name ASC")
    return response.json(result.records if result else [])

@post("/api/members")
async def api_add_member(request, response):
    current_user = get_current_user(request)
    if not current_user:
        return response.json({"error": "Unauthorized"}, 401)
        
    body = request.body or {}
    name = body.get("name", "").strip()
    email = body.get("email", "").strip()
    join_date = body.get("join_date", "").strip() or date.today().isoformat()
    
    if not name or not email:
        return response.json({
            "error": "Bad Request",
            "message": "Name and email are required"
        }, 400)
        
    db = Database()
    existing = db.fetch_one("SELECT * FROM members WHERE email = ?", [email])
    if existing:
        return response.json({
            "error": "Conflict",
            "message": "A member with this email already exists"
        }, 400)
        
    member = Member(
        name=name,
        email=email,
        join_date=join_date
    )
    member.save()
    
    log_change(current_user["id"], "ADD_MEMBER", {"member_id": member.id, "name": name, "email": email})
    
    return response.json(member, 201)

@put("/api/members/{id:int}")
async def api_edit_member(id, request, response):
    current_user = get_current_user(request)
    if not current_user:
        return response.json({"error": "Unauthorized"}, 401)
        
    member = Member.find(id)
    if not member:
        return response.json({"error": "Not Found", "message": "Member not found"}, 404)
        
    body = request.body or {}
    name = body.get("name", "").strip()
    email = body.get("email", "").strip()
    join_date = body.get("join_date", "").strip()
    
    if not name or not email or not join_date:
        return response.json({
            "error": "Bad Request",
            "message": "Name, email, and join date are required"
        }, 400)
        
    db = Database()
    existing = db.fetch_one("SELECT * FROM members WHERE email = ? AND id != ?", [email, id])
    if existing:
        return response.json({
            "error": "Conflict",
            "message": "A member with this email already exists"
        }, 400)
        
    member.name = name
    member.email = email
    member.join_date = join_date
    member.save()
    
    log_change(current_user["id"], "EDIT_MEMBER", {"member_id": id, "name": name, "email": email})
    
    return response.json(member)

@delete("/api/members/{id:int}")
async def api_delete_member(id, request, response):
    current_user = get_current_user(request)
    if not current_user:
        return response.json({"error": "Unauthorized"}, 401)
        
    member = Member.find(id)
    if not member:
        return response.json({"error": "Not Found", "message": "Member not found"}, 404)
        
    name = member.name
    member.delete()
    
    log_change(current_user["id"], "DELETE_MEMBER", {"member_id": id, "name": name})
    
    return response.json({"message": "Member deleted successfully"})

# --- Loans & Returns ---

@post("/api/loans")
async def api_add_loan(request, response):
    current_user = get_current_user(request)
    if not current_user:
        return response.json({"error": "Unauthorized"}, 401)
        
    body = request.body or {}
    book_id = body.get("book_id")
    member_id = body.get("member_id")
    due_date = body.get("due_date", "").strip()
    borrow_date = body.get("borrow_date", "").strip() or date.today().isoformat()
    
    if not book_id or not member_id or not due_date:
        return response.json({
            "error": "Bad Request",
            "message": "Book ID, Member ID, and Due Date are required"
        }, 400)
        
    db = Database()
    
    # 1. Verify Book and Member exist
    book_row = db.fetch_one("SELECT * FROM books WHERE id = ?", [book_id])
    if not book_row:
        return response.json({"error": "Not Found", "message": "Book not found"}, 404)
        
    member_row = db.fetch_one("SELECT * FROM members WHERE id = ?", [member_id])
    if not member_row:
        return response.json({"error": "Not Found", "message": "Member not found"}, 404)
        
    # 2. Check availability: Book cannot be borrowed again until it has been returned
    active_loan = db.fetch_one("SELECT * FROM loans WHERE book_id = ? AND returned = 0", [book_id])
    if active_loan:
        return response.json({
            "error": "Conflict",
            "message": "This book is already out on loan"
        }, 400)
        
    # 3. Create the loan
    loan = Loan(
        book_id=book_id,
        member_id=member_id,
        borrow_date=borrow_date,
        due_date=due_date,
        returned=0,
        staff_id=current_user["id"]
    )
    loan.save()
    
    # Log Audit change
    log_change(
        current_user["id"],
        "RECORD_LOAN",
        {
            "loan_id": loan.id,
            "book_title": book_row["title"],
            "member_name": member_row["name"],
            "due_date": due_date
        }
    )
    
    # 4. Asynchronously email receipt (Push to Queue)
    try:
        queue = Queue(topic="emails")
        queue.push({
            "member_email": member_row["email"],
            "member_name": member_row["name"],
            "book_title": book_row["title"],
            "due_date": due_date
        })
    except Exception as q_err:
        print(f"Failed to queue borrowing receipt email: {q_err}")
        
    return response.json(loan, 201)

@post("/api/loans/{id:int}/return")
async def api_record_return(id, request, response):
    current_user = get_current_user(request)
    if not current_user:
        return response.json({"error": "Unauthorized"}, 401)
        
    loan = Loan.find(id)
    if not loan:
        return response.json({"error": "Not Found", "message": "Loan record not found"}, 404)
        
    if loan.returned == 1:
        return response.json({
            "error": "Conflict",
            "message": "Book has already been returned"
        }, 400)
        
    db = Database()
    book_row = db.fetch_one("SELECT * FROM books WHERE id = ?", [loan.book_id])
    member_row = db.fetch_one("SELECT * FROM members WHERE id = ?", [loan.member_id])
    
    # Record return details
    loan.returned = 1
    loan.returned_date = date.today().isoformat()
    loan.save()
    
    book_title = book_row["title"] if book_row else "Unknown"
    member_name = member_row["name"] if member_row else "Unknown"
    
    log_change(
        current_user["id"],
        "RECORD_RETURN",
        {
            "loan_id": id,
            "book_title": book_title,
            "member_name": member_name
        }
    )
    
    return response.json({"message": "Book returned successfully", "loan": loan})

# --- Audit Logs ---

@secured()
@get("/api/audit-logs")
async def api_list_audit_logs(request, response):
    db = Database()
    sql = """
        SELECT a.*, u.name as staff_name, u.email as staff_email
        FROM audit_logs a
        LEFT JOIN users u ON a.user_id = u.id
        ORDER BY a.created_at DESC
    """
    result = db.fetch(sql)
    return response.json(result.records if result else [])
