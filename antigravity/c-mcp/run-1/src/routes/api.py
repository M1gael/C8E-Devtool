import os
import base64
from datetime import datetime, timedelta
from tina4_python.core.router import get, post, put, delete, noauth, secured
from tina4_python.database import Database
from tina4_python.auth import Auth
from src.app.auth import get_logged_in_staff, log_audit
from tina4_python.queue import Queue
from tina4_python.swagger import description, tags, example, example_response

# Helper to require staff auth in JSON API
def require_api_auth(request, response):
    staff = get_logged_in_staff(request)
    if not staff:
        return None, response({"error": "Unauthorized", "message": "Valid staff authorization token required"}, 401)
    return staff, None

@noauth()
@description("Staff login to obtain JWT token")
@tags(["Authentication"])
@example({"username": "admin", "password": "admin123"})
@example_response(200, {"token": "jwt_token_string", "username": "admin"})
@post("/api/login")
async def api_login(request, response):
    db = Database()
    username = request.body.get("username", "").strip()
    password = request.body.get("password", "")
    
    if not username or not password:
        return response({"error": "Bad Request", "message": "Username and password are required"}, 400)
        
    staff_user = db.fetch_one("SELECT * FROM staff WHERE username = ?", [username])
    if staff_user and Auth.check_password(password, staff_user["password_hash"]):
        token = Auth.get_token_static({
            "staff_id": staff_user["id"],
            "username": staff_user["username"]
        })
        log_audit(staff_user["id"], "API_LOGIN", "staff", staff_user["id"], f"Staff {username} logged in via API.")
        return response({"token": token, "username": username}, 200)
        
    return response({"error": "Unauthorized", "message": "Invalid username or password"}, 401)

@description("Get list of books (public, paginated, searchable)")
@tags(["Books"])
@get("/api/books")
async def api_get_books(request, response):
    db = Database()
    search_query = request.params.get("search", "").strip()
    page = int(request.params.get("page", 1))
    limit = int(request.params.get("limit", 10))
    offset = (page - 1) * limit
    
    where_clause = ""
    params = []
    if search_query:
        where_clause = "WHERE title LIKE ? OR author LIKE ? OR published_year LIKE ?"
        search_param = f"%{search_query}%"
        params = [search_param, search_param, search_param]
        
    count_res = db.fetch_one(f"SELECT COUNT(*) as total FROM books {where_clause}", params)
    total_books = count_res.get("total", 0) if count_res else 0
    
    books_res = db.fetch(f"SELECT * FROM books {where_clause} ORDER BY title ASC LIMIT ? OFFSET ?", params + [limit, offset])
    books = books_res.to_array() if books_res else []
    
    for b in books:
        active_loan = db.fetch_one("SELECT id FROM loans WHERE book_id = ? AND returned_date IS NULL", [b["id"]])
        b["is_available"] = (active_loan is None)
        
    return response({
        "books": books,
        "pagination": {
            "total": total_books,
            "page": page,
            "limit": limit,
            "total_pages": (total_books + limit - 1) // limit
        }
    }, 200)

@description("Get book details and borrowing history")
@tags(["Books"])
@get("/api/books/{id:int}")
async def api_get_book_details(request, response):
    id = int(request.param("id"))
    db = Database()
    book = db.fetch_one("SELECT * FROM books WHERE id = ?", [id])
    if not book:
        return response({"error": "Not Found", "message": "Book not found"}, 404)
        
    active_loan = db.fetch_one("SELECT id FROM loans WHERE book_id = ? AND returned_date IS NULL", [id])
    book["is_available"] = (active_loan is None)
    
    history_res = db.fetch(
        "SELECT l.*, m.name as member_name, m.email as member_email "
        "FROM loans l JOIN members m ON l.member_id = m.id "
        "WHERE l.book_id = ? ORDER BY l.borrow_date DESC", 
        [id]
    )
    loans = history_res.to_array() if history_res else []
    
    return response({
        "book": book,
        "loans": loans
    }, 200)

@secured()
@description("Add a new book (requires staff token)")
@tags(["Books"])
@example({"title": "Clean Code", "author": "Robert C. Martin", "published_year": 2008, "isbn": "978-0132350884", "cover_image_base64": "optional_base64_string", "cover_image_filename": "optional_filename.jpg"})
@post("/api/books")
async def api_add_book(request, response):
    staff, err_resp = require_api_auth(request, response)
    if err_resp: return err_resp
    
    db = Database()
    title = request.body.get("title", "").strip()
    author = request.body.get("author", "").strip()
    published_year = request.body.get("published_year")
    isbn = request.body.get("isbn", "").strip()
    
    if not title or not author or not published_year or not isbn:
        return response({"error": "Bad Request", "message": "title, author, published_year, and isbn are required"}, 400)
        
    cover_path = None
    # Support JSON base64 cover upload
    b64_content = request.body.get("cover_image_base64")
    b64_filename = request.body.get("cover_image_filename", "cover.jpg")
    if b64_content:
        try:
            content = base64.b64decode(b64_content)
            unique_filename = f"{int(datetime.now().timestamp())}_{b64_filename}"
            upload_dir = os.path.join("src", "public", "uploads", "cover_images")
            os.makedirs(upload_dir, exist_ok=True)
            filepath = os.path.join(upload_dir, unique_filename)
            with open(filepath, "wb") as fh:
                fh.write(content)
            cover_path = f"/uploads/cover_images/{unique_filename}"
        except Exception as e:
            return response({"error": "Bad Request", "message": f"Failed to parse base64 cover: {e}"}, 400)
            
    db.insert("books", {
        "title": title,
        "author": author,
        "published_year": int(published_year),
        "isbn": isbn,
        "cover_image": cover_path
    })
    
    new_book = db.fetch_one("SELECT * FROM books WHERE isbn = ? ORDER BY id DESC", [isbn])
    log_audit(staff["staff_id"], "API_ADD_BOOK", "books", new_book["id"], f"Added book: '{title}' (ID {new_book['id']})")
    
    return response(new_book, 201)

@secured()
@description("Edit book properties (requires staff token)")
@tags(["Books"])
@put("/api/books/{id:int}")
async def api_edit_book(request, response):
    id = int(request.param("id"))
    staff, err_resp = require_api_auth(request, response)
    if err_resp: return err_resp
    
    db = Database()
    book = db.fetch_one("SELECT * FROM books WHERE id = ?", [id])
    if not book:
        return response({"error": "Not Found", "message": "Book not found"}, 404)
        
    title = request.body.get("title", book["title"]).strip()
    author = request.body.get("author", book["author"]).strip()
    published_year = request.body.get("published_year", book["published_year"])
    isbn = request.body.get("isbn", book["isbn"]).strip()
    
    update_data = {
        "id": id,
        "title": title,
        "author": author,
        "published_year": int(published_year),
        "isbn": isbn,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    # Optional base64 image update
    b64_content = request.body.get("cover_image_base64")
    b64_filename = request.body.get("cover_image_filename", "cover.jpg")
    if b64_content:
        try:
            content = base64.b64decode(b64_content)
            unique_filename = f"{int(datetime.now().timestamp())}_{b64_filename}"
            upload_dir = os.path.join("src", "public", "uploads", "cover_images")
            os.makedirs(upload_dir, exist_ok=True)
            filepath = os.path.join(upload_dir, unique_filename)
            with open(filepath, "wb") as fh:
                fh.write(content)
            update_data["cover_image"] = f"/uploads/cover_images/{unique_filename}"
        except Exception as e:
            return response({"error": "Bad Request", "message": f"Failed to parse base64 cover: {e}"}, 400)
            
    db.update("books", update_data)
    
    updated_book = db.fetch_one("SELECT * FROM books WHERE id = ?", [id])
    log_audit(staff["staff_id"], "API_EDIT_BOOK", "books", id, f"Updated book: '{title}' (ID {id})")
    
    return response(updated_book, 200)

@secured()
@description("Remove a book (requires staff token)")
@tags(["Books"])
@delete("/api/books/{id:int}")
async def api_delete_book(request, response):
    id = int(request.param("id"))
    staff, err_resp = require_api_auth(request, response)
    if err_resp: return err_resp
    
    db = Database()
    book = db.fetch_one("SELECT * FROM books WHERE id = ?", [id])
    if not book:
        return response({"error": "Not Found", "message": "Book not found"}, 404)
        
    active_loan = db.fetch_one("SELECT id FROM loans WHERE book_id = ? AND returned_date IS NULL", [id])
    if active_loan:
        return response({"error": "Conflict", "message": "Cannot delete book: It is currently out on loan"}, 409)
        
    db.delete("books", {"id": id})
    log_audit(staff["staff_id"], "API_DELETE_BOOK", "books", id, f"Deleted book '{book['title']}' (ID {id})")
    return response({"message": "Book deleted successfully"}, 200)

@secured()
@description("Get list of library members (requires staff token)")
@tags(["Members"])
@get("/api/members")
async def api_get_members(request, response):
    staff, err_resp = require_api_auth(request, response)
    if err_resp: return err_resp
    
    db = Database()
    members_res = db.fetch("SELECT * FROM members ORDER BY name ASC")
    members = members_res.to_array() if members_res else []
    return response(members, 200)

@secured()
@description("Add a member (requires staff token)")
@tags(["Members"])
@example({"name": "Jane Doe", "email": "jane@example.com", "join_date": "2026-07-09"})
@post("/api/members")
async def api_add_member(request, response):
    staff, err_resp = require_api_auth(request, response)
    if err_resp: return err_resp
    
    db = Database()
    name = request.body.get("name", "").strip()
    email = request.body.get("email", "").strip()
    join_date = request.body.get("join_date", "").strip()
    
    if not name or not email or not join_date:
        return response({"error": "Bad Request", "message": "name, email, and join_date are required"}, 400)
        
    existing = db.fetch_one("SELECT id FROM members WHERE email = ?", [email])
    if existing:
        return response({"error": "Conflict", "message": f"Email '{email}' is already registered"}, 409)
        
    db.insert("members", {
        "name": name,
        "email": email,
        "join_date": join_date
    })
    
    new_member = db.fetch_one("SELECT * FROM members WHERE email = ?", [email])
    log_audit(staff["staff_id"], "API_ADD_MEMBER", "members", new_member["id"], f"Registered member: '{name}' (ID {new_member['id']})")
    
    return response(new_member, 201)

@secured()
@description("Edit member properties (requires staff token)")
@tags(["Members"])
@put("/api/members/{id:int}")
async def api_edit_member(request, response):
    id = int(request.param("id"))
    staff, err_resp = require_api_auth(request, response)
    if err_resp: return err_resp
    
    db = Database()
    member = db.fetch_one("SELECT * FROM members WHERE id = ?", [id])
    if not member:
        return response({"error": "Not Found", "message": "Member not found"}, 404)
        
    name = request.body.get("name", member["name"]).strip()
    email = request.body.get("email", member["email"]).strip()
    join_date = request.body.get("join_date", member["join_date"]).strip()
    
    existing = db.fetch_one("SELECT id FROM members WHERE email = ? AND id != ?", [email, id])
    if existing:
        return response({"error": "Conflict", "message": f"Email '{email}' is already registered by another member"}, 409)
        
    db.update("members", {
        "id": id,
        "name": name,
        "email": email,
        "join_date": join_date,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    
    updated_member = db.fetch_one("SELECT * FROM members WHERE id = ?", [id])
    log_audit(staff["staff_id"], "API_EDIT_MEMBER", "members", id, f"Updated member '{name}' (ID {id})")
    
    return response(updated_member, 200)

@secured()
@description("Remove a member (requires staff token)")
@tags(["Members"])
@delete("/api/members/{id:int}")
async def api_delete_member(request, response):
    id = int(request.param("id"))
    staff, err_resp = require_api_auth(request, response)
    if err_resp: return err_resp
    
    db = Database()
    member = db.fetch_one("SELECT * FROM members WHERE id = ?", [id])
    if not member:
        return response({"error": "Not Found", "message": "Member not found"}, 404)
        
    active_loan = db.fetch_one("SELECT id FROM loans WHERE member_id = ? AND returned_date IS NULL", [id])
    if active_loan:
        return response({"error": "Conflict", "message": "Cannot delete member: They currently have active book loans"}, 409)
        
    db.delete("members", {"id": id})
    log_audit(staff["staff_id"], "API_DELETE_MEMBER", "members", id, f"Deleted member '{member['name']}' (ID {id})")
    return response({"message": "Member deleted successfully"}, 200)

@secured()
@description("Record a loan (requires staff token)")
@tags(["Loans"])
@example({"book_id": 1, "member_id": 1, "due_date": "2026-07-23"})
@post("/api/loans")
async def api_record_loan(request, response):
    staff, err_resp = require_api_auth(request, response)
    if err_resp: return err_resp
    
    db = Database()
    book_id = request.body.get("book_id")
    member_id = request.body.get("member_id")
    due_date = request.body.get("due_date")
    
    if not book_id or not member_id or not due_date:
        return response({"error": "Bad Request", "message": "book_id, member_id, and due_date are required"}, 400)
        
    # Check if book is already out on loan
    active_loan = db.fetch_one("SELECT id FROM loans WHERE book_id = ? AND returned_date IS NULL", [int(book_id)])
    if active_loan:
        return response({"error": "Conflict", "message": "This book is already out on loan"}, 409)
        
    # Validate book & member exist
    book = db.fetch_one("SELECT title FROM books WHERE id = ?", [int(book_id)])
    member = db.fetch_one("SELECT name, email FROM members WHERE id = ?", [int(member_id)])
    if not book or not member:
        return response({"error": "Not Found", "message": "Book or Member not found"}, 404)
        
    borrow_date = datetime.now().strftime("%Y-%m-%d")
    
    db.insert("loans", {
        "book_id": int(book_id),
        "member_id": int(member_id),
        "borrow_date": borrow_date,
        "due_date": due_date
    })
    
    new_loan = db.fetch_one("SELECT * FROM loans WHERE book_id = ? AND member_id = ? AND returned_date IS NULL", [int(book_id), int(member_id)])
    
    log_audit(
        staff["staff_id"], 
        "API_CREATE_LOAN", 
        "loans", 
        new_loan["id"], 
        f"Loaned book '{book['title']}' (ID {book_id}) to member '{member['name']}' (ID {member_id}) due on {due_date}"
    )
    
    # Queue receipt email asynchronously
    queue = Queue(topic="emails")
    queue.push({
        "email": member["email"],
        "member_name": member["name"],
        "book_title": book["title"],
        "due_date": due_date
    })
    
    return response(new_loan, 201)

@secured()
@description("Record a return (requires staff token)")
@tags(["Loans"])
@post("/api/loans/return/{loan_id:int}")
async def api_record_return(request, response):
    loan_id = int(request.param("loan_id"))
    staff, err_resp = require_api_auth(request, response)
    if err_resp: return err_resp
    
    db = Database()
    loan = db.fetch_one("SELECT * FROM loans WHERE id = ?", [loan_id])
    if not loan:
        return response({"error": "Not Found", "message": "Loan not found"}, 404)
        
    if loan["returned_date"] is not None:
        return response({"error": "Conflict", "message": "This loan has already been returned"}, 409)
        
    returned_date = datetime.now().strftime("%Y-%m-%d")
    db.update("loans", {
        "id": loan_id,
        "returned_date": returned_date,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    
    book = db.fetch_one("SELECT title FROM books WHERE id = ?", [loan["book_id"]])
    member = db.fetch_one("SELECT name FROM members WHERE id = ?", [loan["member_id"]])
    
    log_audit(
        staff["staff_id"], 
        "API_RETURN_BOOK", 
        "loans", 
        loan_id, 
        f"Returned book '{book['title']}' (ID {loan['book_id']}) from member '{member['name']}' (ID {loan['member_id']})"
    )
    
    updated_loan = db.fetch_one("SELECT * FROM loans WHERE id = ?", [loan_id])
    return response(updated_loan, 200)

@secured()
@description("Get list of staff audit logs (requires staff token)")
@tags(["Audit Trail"])
@get("/api/audit-logs")
async def api_get_audit_logs(request, response):
    staff, err_resp = require_api_auth(request, response)
    if err_resp: return err_resp
    
    db = Database()
    logs_res = db.fetch(
        "SELECT a.*, s.username "
        "FROM audit_logs a JOIN staff s ON a.staff_id = s.id "
        "ORDER BY a.id DESC"
    )
    logs = logs_res.to_array() if logs_res else []
    return response(logs, 200)
