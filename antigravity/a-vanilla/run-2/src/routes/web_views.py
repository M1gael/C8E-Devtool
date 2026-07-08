from tina4_python.core.router import get, noauth
from tina4_python.database.connection import Database
from tina4_python.i18n import I18n
from src.orm.book import Book
from src.orm.member import Member
from src.orm.loan import Loan
from src.orm.audit_log import AuditLog

def get_locale_and_t(request):
    # Determine locale (check query param first, then session, default to English)
    locale = "en"
    lang_param = request.params.get("lang", "").strip().lower()
    
    if lang_param in ("en", "de"):
        locale = lang_param
        if request.session:
            request.session.set("locale", locale)
    elif request.session and request.session.get("locale"):
        locale = request.session.get("locale")
        
    i18n = I18n(locale=locale, path="src/locales")
    return locale, i18n.t

@get("/")
@noauth()
async def catalog_view(request, response):
    locale, t = get_locale_and_t(request)
    db = Database()
    
    q = request.params.get("q", "").strip()
    page = int(request.params.get("page", 1))
    limit = 12  # Show 12 books per page in the grid
    
    sql = "SELECT * FROM books WHERE 1=1"
    sql_count = "SELECT COUNT(*) as total FROM books WHERE 1=1"
    params = []
    
    if q:
        sql += " AND (title LIKE ? OR author LIKE ? OR CAST(published_year AS TEXT) = ? OR isbn = ?)"
        sql_count += " AND (title LIKE ? OR author LIKE ? OR CAST(published_year AS TEXT) = ? OR isbn = ?)"
        term = f"%{q}%"
        params.extend([term, term, q, q])
        
    count_res = db.fetch_one(sql_count, params)
    total_count = count_res["total"] if count_res else 0
    
    sql += " ORDER BY title ASC LIMIT ? OFFSET ?"
    offset = (page - 1) * limit
    records = db.fetch(sql, params + [limit, offset])
    
    books = []
    if records and hasattr(records, "records"):
        recs = records.records
    elif isinstance(records, list):
        recs = records
    else:
        recs = []
        
    for r in recs:
        book = Book()
        book.id = r["id"]
        book.title = r["title"]
        book.author = r["author"]
        book.published_year = r["published_year"]
        book.isbn = r["isbn"]
        book.cover_image = r.get("cover_image", "")
        
        b_dict = book.to_dict()
        b_dict["available"] = book.is_available()
        books.append(b_dict)
        
    pages = (total_count + limit - 1) // limit if limit > 0 else 1
    
    user = request.session.get("user") if request.session else None
    
    return response.render("catalog.html", {
        "t": t,
        "lang": locale,
        "books": books,
        "q": q,
        "page": page,
        "pages": pages,
        "total": total_count,
        "current_user": user
    })

@get("/books/{id:int}")
@noauth()
async def book_detail_view(id, request, response):
    locale, t = get_locale_and_t(request)
    
    book = Book.find_by_id(id)
    if not book:
        return response.redirect("/")
        
    b_dict = book.to_dict()
    b_dict["available"] = book.is_available()
    b_dict["history"] = book.get_history()
    
    user = request.session.get("user") if request.session else None
    
    return response.render("book_detail.html", {
        "t": t,
        "lang": locale,
        "book": b_dict,
        "current_user": user
    })

@get("/login")
@noauth()
async def login_view(request, response):
    locale, t = get_locale_and_t(request)
    
    # Redirect if already logged in
    if request.session and request.session.get("token"):
        return response.redirect("/dashboard")
        
    return response.render("login.html", {
        "t": t,
        "lang": locale,
        "current_user": None
    })

@get("/dashboard")
@noauth() # We handle auth check manually inside the view to redirect clean
async def dashboard_view(request, response):
    locale, t = get_locale_and_t(request)
    
    # Auth redirect
    if not request.session or not request.session.get("token"):
        return response.redirect("/login")
        
    user = request.session.get("user")
    
    # Load data for dashboard
    books = Book.all()
    members = Member.all()
    loans = Loan.all()
    
    # Map lists
    books_list = []
    if books:
        recs = books.records if hasattr(books, "records") else (books if isinstance(books, list) else [])
        for r in recs:
            book = Book()
            book.id = r["id"]
            book.title = r["title"]
            book.author = r["author"]
            book.published_year = r["published_year"]
            book.isbn = r["isbn"]
            book.cover_image = r.get("cover_image", "")
            
            b_dict = book.to_dict()
            b_dict["available"] = book.is_available()
            books_list.append(b_dict)
            
    members_list = []
    if members:
        recs = members.records if hasattr(members, "records") else (members if isinstance(members, list) else [])
        for r in recs:
            members_list.append(r.to_dict() if hasattr(r, "to_dict") else dict(r))
            
    # Active loans (returned = 0)
    active_loans_list = []
    if loans:
        recs = loans.records if hasattr(loans, "records") else (loans if isinstance(loans, list) else [])
        for r in recs:
            if isinstance(r, Loan):
                r_dict = r.to_dict()
            else:
                r_dict = dict(r)
                
            if r_dict.get("returned") == 0:
                # Resolve book and member name
                bk = Book.find_by_id(r_dict["book_id"])
                mb = Member.find_by_id(r_dict["member_id"])
                r_dict["book_title"] = bk.title if bk else "Unknown Book"
                r_dict["member_name"] = mb.name if mb else "Unknown Member"
                active_loans_list.append(r_dict)
                
    return response.render("dashboard.html", {
        "t": t,
        "lang": locale,
        "current_user": user,
        "books": books_list,
        "members": members_list,
        "loans": active_loans_list
    })
