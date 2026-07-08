from tina4_python.core.router import get, noauth, secured
from tina4_python.orm import ORM
from datetime import datetime
import json

def get_session_context(request):
    """Build the base rendering context with locale and session staff details."""
    locale = "en"
    session_staff = None
    
    if request.session:
        locale = request.session.get("locale", "en")
        token = request.session.get("token")
        if token:
            from tina4_python.auth import Auth
            payload = Auth.valid_token_static(token)
            if payload:
                session_staff = {
                    "id": payload.get("staff_id"),
                    "name": payload.get("name")
                }
    
    return {
        "locale": locale,
        "session_staff": session_staff
    }

@noauth()
@get("/")
async def web_catalog(request, response):
    context = get_session_context(request)
    context["active_page"] = "catalog"
    
    db = ORM._get_db()
    q = request.params.get("q", "").strip()
    page = int(request.params.get("page", 1))
    limit = 12
    
    if page < 1:
        page = 1
    offset = (page - 1) * limit

    where_clauses = []
    params = []
    if q:
        where_clauses.append("(title LIKE ? OR author LIKE ? OR CAST(published_year AS TEXT) LIKE ? OR isbn LIKE ?)")
        search_pattern = f"%{q}%"
        params.extend([search_pattern, search_pattern, search_pattern, search_pattern])

    where_sql = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""

    # Count total
    count_row = db.fetch_one("SELECT count(*) as total FROM book" + where_sql, params)
    total_records = count_row.get("total", 0) if count_row else 0
    total_pages = (total_records + limit - 1) // limit

    # Get page records
    books_res = db.fetch(
        f"SELECT * FROM book {where_sql} ORDER BY id DESC LIMIT ? OFFSET ?",
        params + [limit, offset]
    )
    
    books = []
    for row in books_res.records:
        active_loan = db.fetch_one("SELECT id FROM loan WHERE book_id = ? AND returned = 0", [row["id"]])
        row["is_available"] = 1 if not active_loan else 0
        books.append(row)

    context.update({
        "books": books,
        "query_q": q,
        "current_page": page,
        "total_pages": total_pages
    })

    return response.render("pages/index.twig", context)

@noauth()
@get("/book/{id:int}")
async def web_book_detail(id, request, response):
    context = get_session_context(request)
    context["active_page"] = "catalog"

    db = ORM._get_db()
    book = db.fetch_one("SELECT * FROM book WHERE id = ?", [id])
    if not book:
        return response.redirect("/?error=Book not found")

    # Check availability
    active_loan = db.fetch_one("SELECT * FROM loan WHERE book_id = ? AND returned = 0", [id])
    book["is_available"] = 1 if not active_loan else 0
    
    current_loan = None
    if active_loan:
        member = db.fetch_one("SELECT name, email FROM member WHERE id = ?", [active_loan["member_id"]])
        current_loan = {
            "id": active_loan["id"],
            "member_id": active_loan["member_id"],
            "member_name": member["name"] if member else "Unknown",
            "borrow_date": active_loan["borrow_date"],
            "due_date": active_loan["due_date"]
        }

    # Get history
    loans_res = db.fetch(
        "SELECT l.*, m.name as member_name, m.email as member_email "
        "FROM loan l "
        "JOIN member m ON l.member_id = m.id "
        "WHERE l.book_id = ? "
        "ORDER BY l.id DESC",
        [id]
    )
    
    context.update({
        "book": book,
        "current_loan": current_loan,
        "loans": loans_res.records
    })

    return response.render("pages/book.twig", context)

@noauth()
@get("/login")
async def web_login(request, response):
    context = get_session_context(request)
    if context["session_staff"]:
        return response.redirect("/admin")
        
    error = request.params.get("error", "")
    context.update({
        "error_message": error,
        "active_page": "login"
    })
    return response.render("pages/login.twig", context)

@noauth()
@get("/admin")
async def web_admin(request, response):
    context = get_session_context(request)
    if not context["session_staff"]:
        return response.redirect("/login?error=Staff login required")
        
    context["active_page"] = "admin"
    db = ORM._get_db()

    # Get books
    books_res = db.fetch("SELECT * FROM book ORDER BY id DESC")
    books = []
    for row in books_res.records:
        active_loan = db.fetch_one("SELECT id FROM loan WHERE book_id = ? AND returned = 0", [row["id"]])
        row["is_available"] = 1 if not active_loan else 0
        books.append(row)

    # Get members
    members_res = db.fetch("SELECT * FROM member ORDER BY id DESC")
    
    # Get loans
    loans_res = db.fetch(
        "SELECT l.*, b.title as book_title, m.name as member_name "
        "FROM loan l "
        "JOIN book b ON l.book_id = b.id "
        "JOIN member m ON l.member_id = m.id "
        "ORDER BY l.id DESC"
    )

    # Get logs
    logs_res = db.fetch(
        "SELECT a.*, s.name as staff_name "
        "FROM audit_log a "
        "JOIN staff s ON a.staff_id = s.id "
        "ORDER BY a.id DESC LIMIT 100"
    )

    context.update({
        "books": books,
        "members": members_res.records,
        "loans": loans_res.records,
        "audit_logs": logs_res.records
    })

    return response.render("pages/admin.twig", context)

@noauth()
@get("/language/{lang}")
async def web_switch_language(lang, request, response):
    if lang in ("en", "es") and request.session:
        request.session.set("locale", lang)
        request.session.save()
        
    referer = request.headers.get("referer", "/")
    return response.redirect(referer)
