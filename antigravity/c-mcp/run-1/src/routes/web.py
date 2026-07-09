import os
import base64
from datetime import datetime, timedelta
from tina4_python.core.router import get, post, noauth, secured
from tina4_python.database import Database
from tina4_python.auth import Auth
from src.app.auth import get_logged_in_staff, log_audit
from tina4_python.queue import Queue

# Helper to get current locale and staff for templates
def get_base_context(request):
    lang = request.session.get("lang") if request.session else "en"
    if not lang:
        lang = "en"
    staff = get_logged_in_staff(request)
    return {"lang": lang, "staff": staff}

# Save uploaded cover image to src/public/uploads/cover_images
def handle_cover_upload(request):
    uploaded = request.files.get("cover_image_file")
    if not uploaded:
        return None
        
    file_list = uploaded if isinstance(uploaded, list) else [uploaded]
    if not file_list or not file_list[0].get("filename"):
        return None
        
    f = file_list[0]
    filename = f["filename"]
    # Add unique prefix to prevent overwrite
    unique_filename = f"{int(datetime.now().timestamp())}_{filename}"
    content = base64.b64decode(f["content"])
    
    upload_dir = os.path.join("src", "public", "uploads", "cover_images")
    os.makedirs(upload_dir, exist_ok=True)
    
    filepath = os.path.join(upload_dir, unique_filename)
    with open(filepath, "wb") as fh:
        fh.write(content)
        
    return f"/uploads/cover_images/{unique_filename}"

@get("/")
@noauth()
async def index(request, response):
    db = Database()
    ctx = get_base_context(request)
    
    # Search and Pagination
    search_query = request.params.get("search", "").strip()
    page = int(request.params.get("page", 1))
    limit = 12
    offset = (page - 1) * limit
    
    where_clause = ""
    params = []
    if search_query:
        where_clause = "WHERE title LIKE ? OR author LIKE ? OR published_year LIKE ?"
        search_param = f"%{search_query}%"
        params = [search_param, search_param, search_param]
        
    # Get total count for pagination
    count_res = db.fetch_one(f"SELECT COUNT(*) as total FROM books {where_clause}", params)
    total_books = count_res.get("total", 0) if count_res else 0
    total_pages = (total_books + limit - 1) // limit
    
    # Get paginated books
    books_res = db.fetch(f"SELECT * FROM books {where_clause} ORDER BY title ASC LIMIT ? OFFSET ?", params + [limit, offset])
    books = books_res.to_array() if books_res else []
    
    # Check availability status of each book
    for b in books:
        active_loan = db.fetch_one("SELECT id FROM loans WHERE book_id = ? AND returned_date IS NULL", [b["id"]])
        b["is_available"] = (active_loan is None)
        
    ctx.update({
        "books": books,
        "search_query": search_query,
        "current_page": page,
        "total_pages": total_pages,
    })
    return response.render("books.twig", ctx)

@get("/books/{id:int}")
@noauth()
async def book_details(request, response):
    id = int(request.param("id"))
    db = Database()
    ctx = get_base_context(request)
    
    book = db.fetch_one("SELECT * FROM books WHERE id = ?", [id])
    if not book:
        return response("Book not found", 404)
        
    # Check availability
    active_loan = db.fetch_one("SELECT id FROM loans WHERE book_id = ? AND returned_date IS NULL", [id])
    book["is_available"] = (active_loan is None)
    
    # Get borrow history
    history_res = db.fetch(
        "SELECT l.*, m.name as member_name, m.email as member_email "
        "FROM loans l JOIN members m ON l.member_id = m.id "
        "WHERE l.book_id = ? ORDER BY l.borrow_date DESC", 
        [id]
    )
    loans = history_res.to_array() if history_res else []
    
    ctx.update({
        "book": book,
        "loans": loans
    })
    return response.render("book_details.twig", ctx)

@get("/login")
@noauth()
async def login_page(request, response):
    ctx = get_base_context(request)
    if ctx["staff"]:
        return response.redirect("/staff/dashboard")
    return response.render("login.twig", ctx)

@post("/login")
@noauth()
async def login_submit(request, response):
    db = Database()
    ctx = get_base_context(request)
    
    username = request.body.get("username", "").strip()
    password = request.body.get("password", "")
    
    staff_user = db.fetch_one("SELECT * FROM staff WHERE username = ?", [username])
    if staff_user and Auth.check_password(password, staff_user["password_hash"]):
        # Generate token
        token = Auth.get_token_static({
            "staff_id": staff_user["id"],
            "username": staff_user["username"]
        })
        # Store in session
        request.session.set("token", token)
        request.session.set("username", staff_user["username"])
        
        # Log Audit
        log_audit(staff_user["id"], "LOGIN", "staff", staff_user["id"], f"Staff {username} logged in successfully.")
        
        return response.redirect("/staff/dashboard")
        
    ctx["error"] = "Invalid username or password"
    return response.render("login.twig", ctx)

@get("/logout")
@noauth()
async def logout(request, response):
    ctx = get_base_context(request)
    if ctx["staff"]:
        log_audit(ctx["staff"]["staff_id"], "LOGOUT", "staff", ctx["staff"]["staff_id"], f"Staff {ctx['staff']['username']} logged out.")
    
    request.session.delete("token")
    request.session.delete("username")
    return response.redirect("/")

@get("/lang/{code}")
@noauth()
async def set_language(request, response):
    code = request.param("code")
    if code in ("en", "es"):
        request.session.set("lang", code)
    
    referer = request.headers.get("referer", "/")
    return response.redirect(referer)

# SECURED STAFF ROUTES
@get("/staff/dashboard")
@secured()
async def staff_dashboard(request, response):
    db = Database()
    ctx = get_base_context(request)
    if not ctx["staff"]:
        return response.redirect("/login")
        
    # Get metrics
    books_count = db.fetch_one("SELECT COUNT(*) as total FROM books")
    members_count = db.fetch_one("SELECT COUNT(*) as total FROM members")
    active_loans = db.fetch_one("SELECT COUNT(*) as total FROM loans WHERE returned_date IS NULL")
    
    ctx["metrics"] = {
        "total_books": books_count.get("total", 0) if books_count else 0,
        "total_members": members_count.get("total", 0) if members_count else 0,
        "active_loans": active_loans.get("total", 0) if active_loans else 0,
    }
    return response.render("staff/dashboard.twig", ctx)

@get("/staff/books")
@secured()
async def manage_books(request, response):
    db = Database()
    ctx = get_base_context(request)
    if not ctx["staff"]:
        return response.redirect("/login")
        
    # Check for editing
    edit_id = request.params.get("edit")
    edit_book = None
    if edit_id:
        edit_book = db.fetch_one("SELECT * FROM books WHERE id = ?", [int(edit_id)])
        
    books_res = db.fetch("SELECT * FROM books ORDER BY title ASC")
    books = books_res.to_array() if books_res else []
    
    ctx.update({
        "books": books,
        "edit_book": edit_book
    })
    return response.render("staff/books.twig", ctx)

@post("/staff/books/add")
@secured()
async def add_book_submit(request, response):
    db = Database()
    ctx = get_base_context(request)
    if not ctx["staff"]:
        return response.redirect("/login")
        
    title = request.body.get("title", "").strip()
    author = request.body.get("author", "").strip()
    published_year = request.body.get("published_year")
    isbn = request.body.get("isbn", "").strip()
    
    if not title or not author or not published_year or not isbn:
        # Re-render with error
        books_res = db.fetch("SELECT * FROM books ORDER BY title ASC")
        ctx.update({
            "books": books_res.to_array() if books_res else [],
            "error": "All fields are required."
        })
        return response.render("staff/books.twig", ctx)
        
    # Handle cover upload
    cover_path = handle_cover_upload(request)
    
    db.insert("books", {
        "title": title,
        "author": author,
        "published_year": int(published_year),
        "isbn": isbn,
        "cover_image": cover_path
    })
    
    # Get last inserted book ID
    new_book = db.fetch_one("SELECT id FROM books WHERE isbn = ? ORDER BY id DESC", [isbn])
    new_book_id = new_book.get("id") if new_book else None
    
    log_audit(ctx["staff"]["staff_id"], "ADD_BOOK", "books", new_book_id, f"Added book: '{title}' by {author} (ISBN: {isbn})")
    
    return response.redirect("/staff/books")

@post("/staff/books/edit/{id:int}")
@secured()
async def edit_book_submit(request, response):
    id = int(request.param("id"))
    db = Database()
    ctx = get_base_context(request)
    if not ctx["staff"]:
        return response.redirect("/login")
        
    title = request.body.get("title", "").strip()
    author = request.body.get("author", "").strip()
    published_year = request.body.get("published_year")
    isbn = request.body.get("isbn", "").strip()
    
    if not title or not author or not published_year or not isbn:
        return response.redirect(f"/staff/books?edit={id}")
        
    cover_path = handle_cover_upload(request)
    
    # Build update values
    update_data = {
        "id": id,
        "title": title,
        "author": author,
        "published_year": int(published_year),
        "isbn": isbn,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    if cover_path:
        update_data["cover_image"] = cover_path
        
    db.update("books", update_data)
    
    log_audit(ctx["staff"]["staff_id"], "EDIT_BOOK", "books", id, f"Updated book ID {id}: '{title}' by {author}")
    
    return response.redirect("/staff/books")

@post("/staff/books/delete/{id:int}")
@secured()
async def delete_book_submit(request, response):
    id = int(request.param("id"))
    db = Database()
    ctx = get_base_context(request)
    if not ctx["staff"]:
        return response.redirect("/login")
        
    # Check if currently on loan
    active_loan = db.fetch_one("SELECT id FROM loans WHERE book_id = ? AND returned_date IS NULL", [id])
    if active_loan:
        books_res = db.fetch("SELECT * FROM books ORDER BY title ASC")
        ctx.update({
            "books": books_res.to_array() if books_res else [],
            "error": "Cannot delete book: It is currently out on loan."
        })
        return response.render("staff/books.twig", ctx)
        
    book = db.fetch_one("SELECT title FROM books WHERE id = ?", [id])
    title = book.get("title") if book else f"ID {id}"
    
    db.delete("books", {"id": id})
    log_audit(ctx["staff"]["staff_id"], "DELETE_BOOK", "books", id, f"Deleted book: '{title}' (ID {id})")
    
    return response.redirect("/staff/books")

@get("/staff/members")
@secured()
async def manage_members(request, response):
    db = Database()
    ctx = get_base_context(request)
    if not ctx["staff"]:
        return response.redirect("/login")
        
    # Check for editing
    edit_id = request.params.get("edit")
    edit_member = None
    if edit_id:
        edit_member = db.fetch_one("SELECT * FROM members WHERE id = ?", [int(edit_id)])
        
    members_res = db.fetch("SELECT * FROM members ORDER BY name ASC")
    members = members_res.to_array() if members_res else []
    
    ctx.update({
        "members": members,
        "edit_member": edit_member,
        "current_date": datetime.now().strftime("%Y-%m-%d")
    })
    return response.render("staff/members.twig", ctx)

@post("/staff/members/add")
@secured()
async def add_member_submit(request, response):
    db = Database()
    ctx = get_base_context(request)
    if not ctx["staff"]:
        return response.redirect("/login")
        
    name = request.body.get("name", "").strip()
    email = request.body.get("email", "").strip()
    join_date = request.body.get("join_date", "").strip()
    
    if not name or not email or not join_date:
        return response.redirect("/staff/members")
        
    # Check email uniqueness
    existing = db.fetch_one("SELECT id FROM members WHERE email = ?", [email])
    if existing:
        members_res = db.fetch("SELECT * FROM members ORDER BY name ASC")
        ctx.update({
            "members": members_res.to_array() if members_res else [],
            "error": f"Email '{email}' is already registered."
        })
        return response.render("staff/members.twig", ctx)
        
    db.insert("members", {
        "name": name,
        "email": email,
        "join_date": join_date
    })
    
    new_member = db.fetch_one("SELECT id FROM members WHERE email = ?", [email])
    new_member_id = new_member.get("id") if new_member else None
    
    log_audit(ctx["staff"]["staff_id"], "ADD_MEMBER", "members", new_member_id, f"Registered member: '{name}' ({email})")
    
    return response.redirect("/staff/members")

@post("/staff/members/edit/{id:int}")
@secured()
async def edit_member_submit(request, response):
    id = int(request.param("id"))
    db = Database()
    ctx = get_base_context(request)
    if not ctx["staff"]:
        return response.redirect("/login")
        
    name = request.body.get("name", "").strip()
    email = request.body.get("email", "").strip()
    join_date = request.body.get("join_date", "").strip()
    
    if not name or not email or not join_date:
        return response.redirect(f"/staff/members?edit={id}")
        
    # Check email uniqueness for other records
    existing = db.fetch_one("SELECT id FROM members WHERE email = ? AND id != ?", [email, id])
    if existing:
        members_res = db.fetch("SELECT * FROM members ORDER BY name ASC")
        ctx.update({
            "members": members_res.to_array() if members_res else [],
            "error": f"Email '{email}' is already registered by another member."
        })
        return response.render("staff/members.twig", ctx)
        
    db.update("members", {
        "id": id,
        "name": name,
        "email": email,
        "join_date": join_date,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    
    log_audit(ctx["staff"]["staff_id"], "EDIT_MEMBER", "members", id, f"Updated member ID {id}: '{name}' ({email})")
    
    return response.redirect("/staff/members")

@post("/staff/members/delete/{id:int}")
@secured()
async def delete_member_submit(request, response):
    id = int(request.param("id"))
    db = Database()
    ctx = get_base_context(request)
    if not ctx["staff"]:
        return response.redirect("/login")
        
    # Check active loans
    active_loan = db.fetch_one("SELECT id FROM loans WHERE member_id = ? AND returned_date IS NULL", [id])
    if active_loan:
        members_res = db.fetch("SELECT * FROM members ORDER BY name ASC")
        ctx.update({
            "members": members_res.to_array() if members_res else [],
            "error": "Cannot delete member: They currently have active book loans."
        })
        return response.render("staff/members.twig", ctx)
        
    member = db.fetch_one("SELECT name FROM members WHERE id = ?", [id])
    name = member.get("name") if member else f"ID {id}"
    
    db.delete("members", {"id": id})
    log_audit(ctx["staff"]["staff_id"], "DELETE_MEMBER", "members", id, f"Deleted member: '{name}' (ID {id})")
    
    return response.redirect("/staff/members")

@get("/staff/loans")
@secured()
async def manage_loans(request, response):
    db = Database()
    ctx = get_base_context(request)
    if not ctx["staff"]:
        return response.redirect("/login")
        
    # Get all loans
    loans_res = db.fetch(
        "SELECT l.*, b.title as book_title, m.name as member_name, m.email as member_email "
        "FROM loans l JOIN books b ON l.book_id = b.id JOIN members m ON l.member_id = m.id "
        "ORDER BY l.returned_date IS NULL DESC, l.borrow_date DESC"
    )
    loans = loans_res.to_array() if loans_res else []
    
    # Get available books (not currently on loan)
    available_books_res = db.fetch(
        "SELECT * FROM books WHERE id NOT IN (SELECT book_id FROM loans WHERE returned_date IS NULL) ORDER BY title ASC"
    )
    available_books = available_books_res.to_array() if available_books_res else []
    
    # Get all members
    members_res = db.fetch("SELECT * FROM members ORDER BY name ASC")
    members = members_res.to_array() if members_res else []
    
    ctx.update({
        "loans": loans,
        "available_books": available_books,
        "members": members,
        "default_due_date": (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")
    })
    return response.render("staff/loans.twig", ctx)

@post("/staff/loans/add")
@secured()
async def record_loan_submit(request, response):
    db = Database()
    ctx = get_base_context(request)
    if not ctx["staff"]:
        return response.redirect("/login")
        
    book_id = request.body.get("book_id")
    member_id = request.body.get("member_id")
    due_date = request.body.get("due_date")
    
    if not book_id or not member_id or not due_date:
        return response.redirect("/staff/loans")
        
    # double booking check
    active_loan = db.fetch_one("SELECT id FROM loans WHERE book_id = ? AND returned_date IS NULL", [int(book_id)])
    if active_loan:
        ctx["error"] = "This book is already out on loan."
        return response.redirect("/staff/loans")
        
    borrow_date = datetime.now().strftime("%Y-%m-%d")
    
    # Insert loan record
    db.insert("loans", {
        "book_id": int(book_id),
        "member_id": int(member_id),
        "borrow_date": borrow_date,
        "due_date": due_date
    })
    
    # Get information for receipt email queue and audit logs
    book = db.fetch_one("SELECT title FROM books WHERE id = ?", [int(book_id)])
    member = db.fetch_one("SELECT name, email FROM members WHERE id = ?", [int(member_id)])
    
    # Audit log
    new_loan = db.fetch_one("SELECT id FROM loans WHERE book_id = ? AND member_id = ? AND returned_date IS NULL", [int(book_id), int(member_id)])
    new_loan_id = new_loan.get("id") if new_loan else None
    
    log_audit(
        ctx["staff"]["staff_id"], 
        "CREATE_LOAN", 
        "loans", 
        new_loan_id, 
        f"Loaned book '{book['title']}' (ID {book_id}) to member '{member['name']}' (ID {member_id}) due on {due_date}"
    )
    
    # Queue receipt email
    queue = Queue(topic="emails")
    queue.push({
        "email": member["email"],
        "member_name": member["name"],
        "book_title": book["title"],
        "due_date": due_date
    })
    
    return response.redirect("/staff/loans")

@post("/staff/loans/return/{loan_id:int}")
@secured()
async def record_return_submit(request, response):
    loan_id = int(request.param("loan_id"))
    db = Database()
    ctx = get_base_context(request)
    if not ctx["staff"]:
        return response.redirect("/login")
        
    loan = db.fetch_one("SELECT * FROM loans WHERE id = ?", [loan_id])
    if not loan:
        return response.redirect("/staff/loans")
        
    returned_date = datetime.now().strftime("%Y-%m-%d")
    
    db.update("loans", {
        "id": loan_id,
        "returned_date": returned_date,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    
    # Audit
    book = db.fetch_one("SELECT title FROM books WHERE id = ?", [loan["book_id"]])
    member = db.fetch_one("SELECT name FROM members WHERE id = ?", [loan["member_id"]])
    
    log_audit(
        ctx["staff"]["staff_id"], 
        "RETURN_BOOK", 
        "loans", 
        loan_id, 
        f"Returned book '{book['title']}' (ID {loan['book_id']}) from member '{member['name']}' (ID {loan['member_id']})"
    )
    
    return response.redirect("/staff/loans")

@get("/staff/audit")
@secured()
async def view_audit_logs(request, response):
    db = Database()
    ctx = get_base_context(request)
    if not ctx["staff"]:
        return response.redirect("/login")
        
    logs_res = db.fetch(
        "SELECT a.*, s.username "
        "FROM audit_logs a JOIN staff s ON a.staff_id = s.id "
        "ORDER BY a.id DESC"
    )
    logs = logs_res.to_array() if logs_res else []
    
    ctx["logs"] = logs
    return response.render("staff/audit.twig", ctx)
