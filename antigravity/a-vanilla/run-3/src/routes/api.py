import json
from datetime import datetime
from tina4_python.core.router import get, post, put, delete, middleware, noauth, secured
from tina4_python.swagger import description, tags, example, example_response
from tina4_python.auth import Auth, get_token
from tina4_python.validator import Validator
from tina4_python.queue import Queue
from src.middleware.auth import auth_middleware, get_auth_user
from src.orm.book import Book
from src.orm.member import Member
from src.orm.loan import Loan
from src.orm.staff import Staff
from src.orm.audit_log import AuditLog

# Helper to write audit logs
def log_action(staff_id, action, target_id, details=None):
    log = AuditLog()
    log.staff_id = staff_id
    log.action = action
    log.target_id = target_id
    log.details = json.dumps(details) if details else ""
    log.save()

# ================= STAFF AUTHENTICATION =================

@tags("Staff Auth")
@description("Register a new staff member (Development & Testing)")
@example({"name": "Admin Staff", "email": "staff@library.com", "password": "securepassword123"})
@example_response(201, {"message": "Staff registered successfully"})
@example_response(400, {"error": "Invalid input"})
@example_response(409, {"error": "Email already exists"})
@post("/api/register")
@noauth()
async def api_register(request, response):
    v = Validator(request.body)
    v.required("name", "email", "password").email("email").min_length("password", 6)
    if not v.is_valid():
        return response.json({"error": "Validation failed", "errors": v.errors()}, 400)
    
    # Check duplicate
    existing = Staff.where("email = ?", [request.body["email"]])
    if existing:
        return response.json({"error": "Email already exists"}, 409)
        
    staff = Staff()
    staff.name = request.body["name"]
    staff.email = request.body["email"]
    staff.set_password(request.body["password"])
    staff.save()
    
    return response.json({"message": "Staff registered successfully", "staff_id": staff.id}, 201)


@tags("Staff Auth")
@description("Sign in as a staff member to receive a JWT bearer token")
@example({"email": "staff@library.com", "password": "securepassword123"})
@example_response(200, {"token": "JWT_TOKEN", "name": "Admin Staff"})
@example_response(401, {"error": "Invalid credentials"})
@post("/api/login")
@noauth()
async def api_login(request, response):
    body = request.body
    if not body or not body.get("email") or not body.get("password"):
        return response.json({"error": "Email and password are required"}, 400)
        
    staff_list = Staff.where("email = ?", [body["email"]])
    if not staff_list:
        return response.json({"error": "Invalid credentials"}, 401)
        
    staff = staff_list[0]
    if not staff.check_password(body["password"]):
        return response.json({"error": "Invalid credentials"}, 401)
        
    token = get_token({
        "staff_id": staff.id,
        "email": staff.email,
        "name": staff.name
    })
    
    return response.json({
        "message": "Sign-in successful",
        "token": token,
        "staff": {
            "id": staff.id,
            "name": staff.name,
            "email": staff.email
        }
    })

# ================= CATALOG (PUBLIC) =================

@tags("Catalog")
@description("Search and list books from the catalog with pagination")
@example_response(200, {"books": [], "page": 1, "total": 0, "total_pages": 0})
@get("/api/books")
@noauth()
async def api_list_books(request, response):
    search = request.params.get("search", "")
    page = int(request.params.get("page", 1))
    limit = int(request.params.get("limit", 12))
    offset = (page - 1) * limit
    
    if search:
        # Search by title, author, or published_year
        # Handle numeric values for year
        search_year = None
        try:
            search_year = int(search)
        except ValueError:
            pass
            
        if search_year is not None:
            books_list = Book.where("title LIKE ? OR author LIKE ? OR published_year = ?", [f"%{search}%", f"%{search}%", search_year], limit=limit, offset=offset)
            total = Book.count("title LIKE ? OR author LIKE ? OR published_year = ?", [f"%{search}%", f"%{search}%", search_year])
        else:
            books_list = Book.where("title LIKE ? OR author LIKE ?", [f"%{search}%", f"%{search}%"], limit=limit, offset=offset)
            total = Book.count("title LIKE ? OR author LIKE ?", [f"%{search}%", f"%{search}%"])
    else:
        books_list = Book.all(limit=limit, offset=offset)
        total = Book.count()
        
    books_data = []
    for b in books_list:
        b_dict = b.to_dict()
        b_dict["is_available"] = b.is_available
        books_data.append(b_dict)
        
    import math
    total_pages = math.ceil(total / limit) if total > 0 else 0
    
    return response.json({
        "books": books_data,
        "page": page,
        "limit": limit,
        "total": total,
        "total_pages": total_pages
    })


@tags("Catalog")
@description("Get book details by ID including current availability and full loan history")
@example_response(200, {"book": {}, "is_available": True, "loans": []})
@example_response(404, {"error": "Book not found"})
@get("/api/books/{id:int}")
@noauth()
async def api_get_book(request, response):
    id = int(request.params["id"])
    book = Book.find_by_id(id)
    if not book:
        return response.json({"error": "Book not found"}, 404)
        
    # Get all loans history
    loan_records = Loan.where("book_id = ? ORDER BY borrow_date DESC", [id])
    loans_data = []
    for l in loan_records:
        l_dict = l.to_dict()
        # Fetch member info
        member = Member.find_by_id(l.member_id)
        l_dict["member_name"] = member.name if member else "Unknown"
        l_dict["member_email"] = member.email if member else "Unknown"
        loans_data.append(l_dict)
        
    return response.json({
        "book": book.to_dict(),
        "is_available": book.is_available,
        "loans": loans_data
    })

# ================= STAFF BOOKS MANAGEMENT (SECURED) =================

@tags("Staff Books")
@description("Add a new book to the library catalog")
@example({"title": "The Hobbit", "author": "J.R.R. Tolkien", "published_year": 1937, "isbn": "9780007487289", "cover_image": ""})
@example_response(201, {"message": "Book added successfully"})
@example_response(400, {"error": "Validation failed"})
@example_response(401, {"error": "Unauthorized"})
@middleware(auth_middleware)
@post("/api/books")
async def api_create_book(request, response):
    user = await get_auth_user(request)
    if not user:
        return response.json({"error": "Unauthorized. Staff sign-in required."}, 401)
    v = Validator(request.body)
    v.required("title", "author", "published_year", "isbn").integer("published_year")
    if not v.is_valid():
        return response.json({"error": "Validation failed", "errors": v.errors()}, 400)
        
    book = Book()
    book.title = request.body["title"]
    book.author = request.body["author"]
    book.published_year = int(request.body["published_year"])
    book.isbn = request.body["isbn"]
    book.cover_image = request.body.get("cover_image", "")
    book.save()
    
    # Audit log
    log_action(user["staff_id"], "ADD_BOOK", book.id, {"title": book.title, "isbn": book.isbn})
    
    return response.json({"message": "Book added successfully", "book": book.to_dict()}, 201)


@tags("Staff Books")
@description("Update an existing book's details")
@example({"title": "The Hobbit (Collector Edition)", "author": "J.R.R. Tolkien", "published_year": 1937, "isbn": "9780007487289"})
@example_response(200, {"message": "Book updated successfully"})
@example_response(404, {"error": "Book not found"})
@middleware(auth_middleware)
@put("/api/books/{id:int}")
async def api_update_book(request, response):
    user = await get_auth_user(request)
    if not user:
        return response.json({"error": "Unauthorized. Staff sign-in required."}, 401)
    id = int(request.params["id"])
    book = Book.find_by_id(id)
    if not book:
        return response.json({"error": "Book not found"}, 404)
        
    v = Validator(request.body)
    v.required("title", "author", "published_year", "isbn").integer("published_year")
    if not v.is_valid():
        return response.json({"error": "Validation failed", "errors": v.errors()}, 400)
        
    book.title = request.body["title"]
    book.author = request.body["author"]
    book.published_year = int(request.body["published_year"])
    book.isbn = request.body["isbn"]
    book.cover_image = request.body.get("cover_image", "")
    book.save()
    
    # Audit log
    log_action(user["staff_id"], "EDIT_BOOK", book.id, {"title": book.title, "isbn": book.isbn})
    
    return response.json({"message": "Book updated successfully", "book": book.to_dict()})


@tags("Staff Books")
@description("Remove a book from the library catalog")
@example_response(200, {"message": "Book deleted successfully"})
@example_response(404, {"error": "Book not found"})
@middleware(auth_middleware)
@delete("/api/books/{id:int}")
async def api_delete_book(request, response):
    user = await get_auth_user(request)
    if not user:
        return response.json({"error": "Unauthorized. Staff sign-in required."}, 401)
    id = int(request.params["id"])
    book = Book.find_by_id(id)
    if not book:
        return response.json({"error": "Book not found"}, 404)
        
    title = book.title
    book.delete()
    
    # Audit log
    log_action(user["staff_id"], "DELETE_BOOK", id, {"title": title})
    
    return response.json({"message": "Book deleted successfully"})

# ================= STAFF MEMBERS MANAGEMENT (SECURED) =================

@tags("Staff Members")
@description("Add a new member to the library")
@example({"name": "John Doe", "email": "john.doe@example.com"})
@example_response(201, {"message": "Member added successfully"})
@middleware(auth_middleware)
@post("/api/members")
async def api_create_member(request, response):
    user = await get_auth_user(request)
    if not user:
        return response.json({"error": "Unauthorized. Staff sign-in required."}, 401)
    v = Validator(request.body)
    v.required("name", "email").email("email")
    if not v.is_valid():
        return response.json({"error": "Validation failed", "errors": v.errors()}, 400)
        
    # Check duplicate
    existing = Member.where("email = ?", [request.body["email"]])
    if existing:
        return response.json({"error": "Member email already exists"}, 409)
        
    member = Member()
    member.name = request.body["name"]
    member.email = request.body["email"]
    member.join_date = datetime.now().strftime("%Y-%m-%d")
    member.save()
    
    # Audit log
    log_action(user["staff_id"], "ADD_MEMBER", member.id, {"name": member.name, "email": member.email})
    
    return response.json({"message": "Member added successfully", "member": member.to_dict()}, 201)


@tags("Staff Members")
@description("List all library members")
@middleware(auth_middleware)
@get("/api/members")
async def api_list_members(request, response):
    user = await get_auth_user(request)
    if not user:
        return response.json({"error": "Unauthorized. Staff sign-in required."}, 401)
    members = Member.all()
    return response.json({"members": [m.to_dict() for m in members]})


@tags("Staff Members")
@description("Update a member's details")
@example({"name": "Johnathan Doe", "email": "john.doe@example.com"})
@middleware(auth_middleware)
@put("/api/members/{id:int}")
async def api_update_member(request, response):
    user = await get_auth_user(request)
    if not user:
        return response.json({"error": "Unauthorized. Staff sign-in required."}, 401)
    id = int(request.params["id"])
    member = Member.find_by_id(id)
    if not member:
        return response.json({"error": "Member not found"}, 404)
        
    v = Validator(request.body)
    v.required("name", "email").email("email")
    if not v.is_valid():
        return response.json({"error": "Validation failed", "errors": v.errors()}, 400)
        
    # Check duplicate email on other members
    existing = Member.where("email = ? AND id != ?", [request.body["email"], id])
    if existing:
        return response.json({"error": "Email already in use by another member"}, 409)
        
    member.name = request.body["name"]
    member.email = request.body["email"]
    member.save()
    
    # Audit log
    log_action(user["staff_id"], "EDIT_MEMBER", member.id, {"name": member.name, "email": member.email})
    
    return response.json({"message": "Member updated successfully", "member": member.to_dict()})


@tags("Staff Members")
@description("Remove a member from the library")
@middleware(auth_middleware)
@delete("/api/members/{id:int}")
async def api_delete_member(request, response):
    user = await get_auth_user(request)
    if not user:
        return response.json({"error": "Unauthorized. Staff sign-in required."}, 401)
    id = int(request.params["id"])
    member = Member.find_by_id(id)
    if not member:
        return response.json({"error": "Member not found"}, 404)
        
    name = member.name
    member.delete()
    
    # Audit log
    log_action(user["staff_id"], "DELETE_MEMBER", id, {"name": name})
    
    return response.json({"message": "Member deleted successfully"})

# ================= STAFF LOANS & RETURNS (SECURED) =================

@tags("Staff Loans")
@description("Record a new book loan. Queues a receipt email and returns immediately.")
@example({"book_id": 1, "member_id": 1, "due_date": "2026-07-22"})
@example_response(201, {"message": "Loan recorded successfully"})
@example_response(400, {"error": "Book is already out on loan"})
@middleware(auth_middleware)
@post("/api/loans")
async def api_create_loan(request, response):
    user = await get_auth_user(request)
    if not user:
        return response.json({"error": "Unauthorized. Staff sign-in required."}, 401)
    v = Validator(request.body)
    v.required("book_id", "member_id", "due_date").integer("book_id").integer("member_id")
    if not v.is_valid():
        return response.json({"error": "Validation failed", "errors": v.errors()}, 400)
        
    book = Book.find_by_id(request.body["book_id"])
    if not book:
        return response.json({"error": "Book not found"}, 404)
        
    member = Member.find_by_id(request.body["member_id"])
    if not member:
        return response.json({"error": "Member not found"}, 404)
        
    # Check if book is already borrowed
    if not book.is_available:
        return response.json({"error": "Book is already out on loan"}, 400)
        
    loan = Loan()
    loan.book_id = book.id
    loan.member_id = member.id
    loan.borrow_date = datetime.now().strftime("%Y-%m-%d")
    loan.due_date = request.body["due_date"]
    loan.returned = 0
    loan.save()
    
    # Queue the receipt email
    email_queue = Queue(topic="loans_email")
    email_queue.push({
        "member_name": member.name,
        "member_email": member.email,
        "book_title": book.title,
        "borrow_date": loan.borrow_date,
        "due_date": loan.due_date
    })
    
    # Audit log
    log_action(user["staff_id"], "BORROW_BOOK", loan.id, {
        "book_id": book.id,
        "book_title": book.title,
        "member_id": member.id,
        "member_name": member.name,
        "due_date": loan.due_date
    })
    
    return response.json({"message": "Loan recorded successfully", "loan": loan.to_dict()}, 201)


@tags("Staff Loans")
@description("Record returning a borrowed book")
@example_response(200, {"message": "Return recorded successfully"})
@example_response(400, {"error": "Loan already returned"})
@example_response(404, {"error": "Loan not found"})
@middleware(auth_middleware)
@post("/api/loans/return/{id:int}")
async def api_return_loan(request, response):
    user = await get_auth_user(request)
    if not user:
        return response.json({"error": "Unauthorized. Staff sign-in required."}, 401)
    id = int(request.params["id"])
    loan = Loan.find_by_id(id)
    if not loan:
        return response.json({"error": "Loan not found"}, 404)
        
    if loan.returned == 1:
        return response.json({"error": "Book has already been returned"}, 400)
        
    book = Book.find_by_id(loan.book_id)
    member = Member.find_by_id(loan.member_id)
    
    loan.returned = 1
    loan.returned_date = datetime.now().strftime("%Y-%m-%d")
    loan.save()
    
    # Audit log
    log_action(user["staff_id"], "RETURN_BOOK", loan.id, {
        "book_id": book.id if book else loan.book_id,
        "book_title": book.title if book else "Unknown",
        "member_id": member.id if member else loan.member_id,
        "member_name": member.name if member else "Unknown"
    })
    
    return response.json({"message": "Return recorded successfully", "loan": loan.to_dict()})

# ================= STAFF AUDIT LOGS (SECURED) =================

@tags("Staff Logs")
@description("Get recent library audit logs")
@middleware(auth_middleware)
@get("/api/audit-logs")
async def api_list_logs(request, response):
    user = await get_auth_user(request)
    if not user:
        return response.json({"error": "Unauthorized. Staff sign-in required."}, 401)
    logs = AuditLog.all()
    logs_data = []
    for l in logs:
        l_dict = l.to_dict()
        staff = Staff.find_by_id(l.staff_id)
        l_dict["staff_name"] = staff.name if staff else "System"
        logs_data.append(l_dict)
    return response.json({"audit_logs": logs_data})
