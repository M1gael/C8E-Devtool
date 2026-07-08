import math
from datetime import datetime
from tina4_python.core.router import get, post
from tina4_python.i18n import I18n
from tina4_python.queue import Queue
from src.orm.book import Book
from src.orm.member import Member
from src.orm.loan import Loan
from src.orm.staff import Staff
from src.orm.audit_log import AuditLog

# Helper to log actions
def log_action(staff_id, action, target_id, details=None):
    import json
    log = AuditLog()
    log.staff_id = staff_id
    log.action = action
    log.target_id = target_id
    log.details = json.dumps(details) if details else ""
    log.save()

# Context builder for templates
def get_web_context(request):
    lang = request.params.get("lang")
    lang_changed = False
    if lang:
        lang_changed = True
    else:
        lang = request.cookies.get("lang", "en")
        
    if lang not in ["en", "es"]:
        lang = "en"
        
    i18n = I18n(locale=lang, path="src/locales")
    
    staff = None
    staff_id = request.session.get("staff_id") if (hasattr(request, "session") and request.session) else None
    if staff_id:
        staff = Staff.find_by_id(staff_id)
        
    flash_message = request.session.get("flash_message") if (hasattr(request, "session") and request.session) else None
    flash_type = request.session.get("flash_type") if (hasattr(request, "session") and request.session) else None
    
    if flash_message:
        del request.session["flash_message"]
        del request.session["flash_type"]
        
    return {
        "t": i18n.t,
        "current_lang": lang,
        "lang_changed": lang_changed,
        "staff": staff,
        "flash_message": flash_message,
        "flash_type": flash_type
    }

def apply_lang_cookie(res, context):
    if context["lang_changed"]:
        return res.cookie("lang", context["current_lang"], path="/")
    return res

# ================= PUBLIC ROUTES =================

@get("/")
async def web_catalog(request, response):
    ctx = get_web_context(request)
    
    search = request.params.get("search", "")
    page = int(request.params.get("page", 1))
    limit = 12
    offset = (page - 1) * limit
    
    if search:
        search_year = None
        try:
            search_year = int(search)
        except ValueError:
            pass
            
        if search_year is not None:
            books = Book.where("title LIKE ? OR author LIKE ? OR published_year = ?", [f"%{search}%", f"%{search}%", search_year], limit=limit, offset=offset)
            total = Book.count("title LIKE ? OR author LIKE ? OR published_year = ?", [f"%{search}%", f"%{search}%", search_year])
        else:
            books = Book.where("title LIKE ? OR author LIKE ?", [f"%{search}%", f"%{search}%"], limit=limit, offset=offset)
            total = Book.count("title LIKE ? OR author LIKE ?", [f"%{search}%", f"%{search}%"])
    else:
        books = Book.all(limit=limit, offset=offset)
        total = Book.count()
        
    books_data = []
    for b in books:
        b_dict = b.to_dict()
        b_dict["is_available"] = b.is_available
        books_data.append(b_dict)
        
    total_pages = math.ceil(total / limit) if total > 0 else 0
    has_prev = page > 1
    has_next = page < total_pages
    
    ctx.update({
        "books": books_data,
        "query": search,
        "page": page,
        "total_pages": total_pages,
        "has_prev": has_prev,
        "has_next": has_next
    })
    
    res = response.render("catalog.html", ctx)
    return apply_lang_cookie(res, ctx)


@get("/books/{id:int}")
async def web_book_detail(request, response):
    id = int(request.params["id"])
    ctx = get_web_context(request)
    
    book = Book.find_by_id(id)
    if not book:
        request.session["flash_message"] = "Book not found."
        request.session["flash_type"] = "error"
        return response.redirect("/")
        
    loan_records = Loan.where("book_id = ? ORDER BY borrow_date DESC", [id])
    loans_data = []
    for l in loan_records:
        l_dict = l.to_dict()
        member = Member.find_by_id(l.member_id)
        l_dict["member_name"] = member.name if member else "Unknown"
        l_dict["member_email"] = member.email if member else "Unknown"
        loans_data.append(l_dict)
        
    ctx.update({
        "book": book.to_dict(),
        "is_available": book.is_available,
        "active_loan": book.active_loan,
        "loans": loans_data
    })
    
    res = response.render("book_detail.html", ctx)
    return apply_lang_cookie(res, ctx)

# ================= STAFF AUTHENTICATION (WEB) =================

@get("/login")
async def web_login_form(request, response):
    ctx = get_web_context(request)
    if ctx["staff"]:
        return response.redirect("/dashboard")
        
    res = response.render("login.html", ctx)
    return apply_lang_cookie(res, ctx)


@post("/login")
async def web_login_action(request, response):
    body = request.body
    email = body.get("email", "")
    password = body.get("password", "")
    
    staff_list = Staff.where("email = ?", [email])
    if staff_list:
        staff = staff_list[0]
        if staff.check_password(password):
            request.session["staff_id"] = staff.id
            request.session["flash_message"] = "Welcome back, " + staff.name + "!"
            request.session["flash_type"] = "success"
            
            # Also set JWT token in a cookie
            token = get_token({
                "staff_id": staff.id,
                "email": staff.email,
                "name": staff.name
            })
            return response.cookie("token", token, path="/").redirect("/dashboard")
            
    request.session["flash_message"] = "Invalid email or password."
    request.session["flash_type"] = "error"
    return response.redirect("/login")


@get("/logout")
async def web_logout_action(request, response):
    if hasattr(request, "session") and request.session:
        request.session.clear()
    return response.cookie("token", "", max_age=0, path="/").redirect("/")

# ================= STAFF PORTAL (SECURED) =================

@get("/dashboard")
async def web_dashboard(request, response):
    ctx = get_web_context(request)
    if not ctx["staff"]:
        request.session["flash_message"] = "Please sign in to access the staff portal."
        request.session["flash_type"] = "error"
        return response.redirect("/login")
        
    # Get active loans
    loans = Loan.where("returned = 0 ORDER BY borrow_date DESC")
    active_loans = []
    for l in loans:
        l_dict = l.to_dict()
        book = Book.find_by_id(l.book_id)
        member = Member.find_by_id(l.member_id)
        l_dict["book_title"] = book.title if book else "Unknown Book"
        l_dict["member_name"] = member.name if member else "Unknown Member"
        l_dict["member_email"] = member.email if member else ""
        active_loans.append(l_dict)
        
    # Get audit logs
    logs = AuditLog.all(limit=25, offset=0)
    audit_logs = []
    for l in logs:
        l_dict = l.to_dict()
        staff = Staff.find_by_id(l.staff_id)
        l_dict["staff_name"] = staff.name if staff else "System"
        audit_logs.append(l_dict)
        
    ctx.update({
        "active_loans": active_loans,
        "audit_logs": audit_logs
    })
    
    res = response.render("dashboard.html", ctx)
    return apply_lang_cookie(res, ctx)


@get("/dashboard/books")
async def web_manage_books(request, response):
    ctx = get_web_context(request)
    if not ctx["staff"]:
        return response.redirect("/login")
        
    books = Book.all()
    books_data = []
    for b in books:
        b_dict = b.to_dict()
        b_dict["is_available"] = b.is_available
        books_data.append(b_dict)
        
    ctx.update({
        "books": books_data
    })
    
    res = response.render("staff_books.html", ctx)
    return apply_lang_cookie(res, ctx)


@post("/books/save")
async def web_save_book(request, response):
    ctx = get_web_context(request)
    if not ctx["staff"]:
        return response.redirect("/login")
        
    body = request.body
    book_id = body.get("id")
    title = body.get("title", "")
    author = body.get("author", "")
    published_year = body.get("published_year")
    isbn = body.get("isbn", "")
    cover_image = body.get("cover_image", "")
    
    if not title or not author or not published_year or not isbn:
        request.session["flash_message"] = "All fields (except cover image) are required."
        request.session["flash_type"] = "error"
        return response.redirect("/dashboard/books")
        
    try:
        published_year = int(published_year)
    except ValueError:
        request.session["flash_message"] = "Published year must be a valid number."
        request.session["flash_type"] = "error"
        return response.redirect("/dashboard/books")
        
    if book_id:
        # Edit
        book = Book.find_by_id(int(book_id))
        if not book:
            request.session["flash_message"] = "Book not found."
            request.session["flash_type"] = "error"
            return response.redirect("/dashboard/books")
        action = "EDIT_BOOK"
    else:
        # Create
        book = Book()
        action = "ADD_BOOK"
        
    book.title = title
    book.author = author
    book.published_year = published_year
    book.isbn = isbn
    book.cover_image = cover_image
    book.save()
    
    log_action(ctx["staff"].id, action, book.id, {"title": book.title, "isbn": book.isbn})
    
    request.session["flash_message"] = "Book details saved successfully."
    request.session["flash_type"] = "success"
    return response.redirect("/dashboard/books")


@post("/books/delete/{id:int}")
async def web_delete_book(request, response):
    id = int(request.params["id"])
    ctx = get_web_context(request)
    if not ctx["staff"]:
        return response.redirect("/login")
        
    book = Book.find_by_id(id)
    if not book:
        request.session["flash_message"] = "Book not found."
        request.session["flash_type"] = "error"
        return response.redirect("/dashboard/books")
        
    title = book.title
    book.delete()
    
    log_action(ctx["staff"].id, "DELETE_BOOK", id, {"title": title})
    
    request.session["flash_message"] = "Book deleted successfully."
    request.session["flash_type"] = "success"
    return response.redirect("/dashboard/books")


@get("/dashboard/members")
async def web_manage_members(request, response):
    ctx = get_web_context(request)
    if not ctx["staff"]:
        return response.redirect("/login")
        
    members = Member.all()
    ctx.update({
        "members": [m.to_dict() for m in members]
    })
    
    res = response.render("staff_members.html", ctx)
    return apply_lang_cookie(res, ctx)


@post("/members/save")
async def web_save_member(request, response):
    ctx = get_web_context(request)
    if not ctx["staff"]:
        return response.redirect("/login")
        
    body = request.body
    member_id = body.get("id")
    name = body.get("name", "")
    email = body.get("email", "")
    
    if not name or not email:
        request.session["flash_message"] = "Name and email are required."
        request.session["flash_type"] = "error"
        return response.redirect("/dashboard/members")
        
    if member_id:
        member = Member.find_by_id(int(member_id))
        if not member:
            request.session["flash_message"] = "Member not found."
            request.session["flash_type"] = "error"
            return response.redirect("/dashboard/members")
        action = "EDIT_MEMBER"
        
        # Check duplicate on others
        dup = Member.where("email = ? AND id != ?", [email, member.id])
        if dup:
            request.session["flash_message"] = "Email address already exists."
            request.session["flash_type"] = "error"
            return response.redirect("/dashboard/members")
    else:
        member = Member()
        member.join_date = datetime.now().strftime("%Y-%m-%d")
        action = "ADD_MEMBER"
        
        # Check duplicate
        dup = Member.where("email = ?", [email])
        if dup:
            request.session["flash_message"] = "Email address already exists."
            request.session["flash_type"] = "error"
            return response.redirect("/dashboard/members")
            
    member.name = name
    member.email = email
    member.save()
    
    log_action(ctx["staff"].id, action, member.id, {"name": member.name, "email": member.email})
    
    request.session["flash_message"] = "Member details saved successfully."
    request.session["flash_type"] = "success"
    return response.redirect("/dashboard/members")


@post("/members/delete/{id:int}")
async def web_delete_member(request, response):
    id = int(request.params["id"])
    ctx = get_web_context(request)
    if not ctx["staff"]:
        return response.redirect("/login")
        
    member = Member.find_by_id(id)
    if not member:
        request.session["flash_message"] = "Member not found."
        request.session["flash_type"] = "error"
        return response.redirect("/dashboard/members")
        
    name = member.name
    member.delete()
    
    log_action(ctx["staff"].id, "DELETE_MEMBER", id, {"name": name})
    
    request.session["flash_message"] = "Member deleted successfully."
    request.session["flash_type"] = "success"
    return response.redirect("/dashboard/members")


@get("/dashboard/loans")
async def web_manage_loans(request, response):
    ctx = get_web_context(request)
    if not ctx["staff"]:
        return response.redirect("/login")
        
    # Get available books for the dropdown
    all_books = Book.all()
    available_books = [b.to_dict() for b in all_books if b.is_available]
    
    # Get all members
    members = Member.all()
    
    # Get active loans
    loans = Loan.where("returned = 0 ORDER BY borrow_date DESC")
    active_loans = []
    for l in loans:
        l_dict = l.to_dict()
        book = Book.find_by_id(l.book_id)
        member = Member.find_by_id(l.member_id)
        l_dict["book_title"] = book.title if book else "Unknown Book"
        l_dict["member_name"] = member.name if member else "Unknown Member"
        l_dict["member_email"] = member.email if member else ""
        active_loans.append(l_dict)
        
    ctx.update({
        "available_books": available_books,
        "members": [m.to_dict() for m in members],
        "active_loans": active_loans
    })
    
    res = response.render("staff_loans.html", ctx)
    return apply_lang_cookie(res, ctx)


@post("/loans/create")
async def web_create_loan(request, response):
    ctx = get_web_context(request)
    if not ctx["staff"]:
        return response.redirect("/login")
        
    body = request.body
    book_id = body.get("book_id")
    member_id = body.get("member_id")
    due_date = body.get("due_date", "")
    
    if not book_id or not member_id or not due_date:
        request.session["flash_message"] = "All fields are required to record a loan."
        request.session["flash_type"] = "error"
        return response.redirect("/dashboard/loans")
        
    book = Book.find_by_id(int(book_id))
    member = Member.find_by_id(int(member_id))
    
    if not book or not member:
        request.session["flash_message"] = "Selected book or member was not found."
        request.session["flash_type"] = "error"
        return response.redirect("/dashboard/loans")
        
    if not book.is_available:
        request.session["flash_message"] = "Selected book is already out on loan."
        request.session["flash_type"] = "error"
        return response.redirect("/dashboard/loans")
        
    loan = Loan()
    loan.book_id = book.id
    loan.member_id = member.id
    loan.borrow_date = datetime.now().strftime("%Y-%m-%d")
    loan.due_date = due_date
    loan.returned = 0
    loan.save()
    
    # Queue receipt email
    email_queue = Queue(topic="loans_email")
    email_queue.push({
        "member_name": member.name,
        "member_email": member.email,
        "book_title": book.title,
        "borrow_date": loan.borrow_date,
        "due_date": loan.due_date
    })
    
    log_action(ctx["staff"].id, "BORROW_BOOK", loan.id, {
        "book_id": book.id,
        "book_title": book.title,
        "member_id": member.id,
        "member_name": member.name,
        "due_date": loan.due_date
    })
    
    request.session["flash_message"] = "Loan recorded successfully and receipt queued."
    request.session["flash_type"] = "success"
    return response.redirect("/dashboard/loans")


@post("/loans/return/{id:int}")
async def web_return_loan(request, response):
    id = int(request.params["id"])
    ctx = get_web_context(request)
    if not ctx["staff"]:
        return response.redirect("/login")
        
    loan = Loan.find_by_id(id)
    if not loan:
        request.session["flash_message"] = "Loan record not found."
        request.session["flash_type"] = "error"
        return response.redirect("/dashboard")
        
    if loan.returned == 1:
        request.session["flash_message"] = "Book was already returned."
        request.session["flash_type"] = "error"
        return response.redirect("/dashboard")
        
    book = Book.find_by_id(loan.book_id)
    member = Member.find_by_id(loan.member_id)
    
    loan.returned = 1
    loan.returned_date = datetime.now().strftime("%Y-%m-%d")
    loan.save()
    
    log_action(ctx["staff"].id, "RETURN_BOOK", loan.id, {
        "book_id": book.id if book else loan.book_id,
        "book_title": book.title if book else "Unknown",
        "member_id": member.id if member else loan.member_id,
        "member_name": member.name if member else "Unknown"
    })
    
    request.session["flash_message"] = "Book return recorded successfully."
    request.session["flash_type"] = "success"
    
    # Redirect back to where the request came from
    referer = request.headers.get("referer", "/dashboard")
    return response.redirect(referer)
