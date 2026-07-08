from tina4_python.core.router import get, post
from tina4_python.orm import ORM
from tina4_python.queue import Queue
from src.app.helpers import get_current_staff, log_change
from datetime import datetime
import json

@post("/api/loans")
async def borrow_book(request, response):
    staff = get_current_staff(request)
    if not staff:
        return response({"error": "Unauthorized", "message": "Valid staff session or token required"}, 401)

    body = request.body or {}
    book_id = body.get("book_id")
    member_id = body.get("member_id")
    due_date = body.get("due_date", "").strip()

    # Validate inputs
    errors = []
    if not book_id:
        errors.append("Book ID is required")
    if not member_id:
        errors.append("Member ID is required")
    if not due_date:
        errors.append("Due date is required")
    else:
        try:
            datetime.strptime(due_date, "%Y-%m-%d")
        except ValueError:
            errors.append("Due date must be in YYYY-MM-DD format")

    if errors:
        return response({"error": "Validation Error", "message": "; ".join(errors)}, 400)

    db = ORM._get_db()
    
    # Check book exists
    book = db.fetch_one("SELECT * FROM book WHERE id = ?", [book_id])
    if not book:
        return response({"error": "Not Found", "message": f"Book with ID {book_id} not found"}, 404)
        
    # Check member exists
    member = db.fetch_one("SELECT * FROM member WHERE id = ?", [member_id])
    if not member:
        return response({"error": "Not Found", "message": f"Member with ID {member_id} not found"}, 404)

    # Check if book is already borrowed
    active_loan = db.fetch_one("SELECT id FROM loan WHERE book_id = ? AND returned = 0", [book_id])
    if active_loan:
        return response({"error": "Conflict", "message": "Book is already out on loan and cannot be borrowed again until returned"}, 409)

    # Record the loan
    today_str = datetime.now().strftime("%Y-%m-%d")
    db.execute(
        "INSERT INTO loan (member_id, book_id, borrow_date, due_date, returned) VALUES (?, ?, ?, ?, 0)",
        [member_id, book_id, today_str, due_date]
    )
    db.commit()
    
    new_loan = db.fetch_one("SELECT id FROM loan WHERE book_id = ? AND member_id = ? AND returned = 0 ORDER BY id DESC LIMIT 1", [book_id, member_id])
    loan_id = new_loan["id"] if new_loan else 0

    # Log action
    log_change(staff["staff_id"], "record_loan", "loan", loan_id, {
        "book_id": book_id,
        "book_title": book["title"],
        "member_id": member_id,
        "member_name": member["name"],
        "due_date": due_date
    })

    # Queue receipt email - runs immediately/asynchronously
    try:
        queue = Queue(topic="emails")
        queue.push({
            "to": member["email"],
            "member_name": member["name"],
            "book_title": book["title"],
            "due_date": due_date
        })
    except Exception as e:
        # Don't fail the borrow request if queue pushing fails, just log it
        from tina4_python.debug import Log
        Log.error(f"Failed to queue borrowing receipt email: {e}")

    return response({"message": "Loan recorded successfully", "loan_id": loan_id}, 201)

@post("/api/loans/{id:int}/return")
async def return_book(id, request, response):
    staff = get_current_staff(request)
    if not staff:
        return response({"error": "Unauthorized", "message": "Valid staff session or token required"}, 401)

    db = ORM._get_db()
    loan = db.fetch_one("SELECT * FROM loan WHERE id = ?", [id])
    if not loan:
        return response({"error": "Not Found", "message": f"Loan with ID {id} not found"}, 404)

    if loan["returned"] == 1:
        return response({"error": "Conflict", "message": "Book has already been returned for this loan"}, 409)

    # Record return
    today_str = datetime.now().strftime("%Y-%m-%d")
    db.execute(
        "UPDATE loan SET returned = 1, returned_date = ? WHERE id = ?",
        [today_str, id]
    )
    db.commit()

    # Get book and member details
    book = db.fetch_one("SELECT title FROM book WHERE id = ?", [loan["book_id"]])
    member = db.fetch_one("SELECT name FROM member WHERE id = ?", [loan["member_id"]])

    # Log action
    log_change(staff["staff_id"], "record_return", "loan", id, {
        "book_id": loan["book_id"],
        "book_title": book["title"] if book else "Unknown",
        "member_id": loan["member_id"],
        "member_name": member["name"] if member else "Unknown"
    })

    return response({"message": "Book returned successfully"})

@get("/api/loans")
async def list_loans(request, response):
    staff = get_current_staff(request)
    if not staff:
        return response({"error": "Unauthorized", "message": "Valid staff session or token required"}, 401)

    db = ORM._get_db()
    
    loans_res = db.fetch(
        "SELECT l.*, b.title as book_title, m.name as member_name "
        "FROM loan l "
        "JOIN book b ON l.book_id = b.id "
        "JOIN member m ON l.member_id = m.id "
        "ORDER BY l.id DESC"
    )
    
    return response(loans_res.records)

@get("/api/audit-logs")
async def list_audit_logs(request, response):
    staff = get_current_staff(request)
    if not staff:
        return response({"error": "Unauthorized", "message": "Valid staff session or token required"}, 401)

    db = ORM._get_db()
    logs_res = db.fetch(
        "SELECT a.*, s.name as staff_name "
        "FROM audit_log a "
        "JOIN staff s ON a.staff_id = s.id "
        "ORDER BY a.id DESC"
    )
    return response(logs_res.records)
