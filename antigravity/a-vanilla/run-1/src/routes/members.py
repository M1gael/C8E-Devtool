from tina4_python.core.router import get, post, put, delete
from tina4_python.orm import ORM
from src.app.helpers import get_current_staff, log_change
from datetime import datetime
import re

@get("/api/members")
async def list_members(request, response):
    staff = get_current_staff(request)
    if not staff:
        return response({"error": "Unauthorized", "message": "Valid staff session or token required"}, 401)

    db = ORM._get_db()
    q = request.params.get("q", "").strip()
    page = int(request.params.get("page", 1))
    limit = int(request.params.get("limit", 20))
    
    if page < 1:
        page = 1
    if limit < 1:
        limit = 20
        
    offset = (page - 1) * limit

    where_clauses = []
    params = []
    if q:
        where_clauses.append("(name LIKE ? OR email LIKE ?)")
        search_pattern = f"%{q}%"
        params.extend([search_pattern, search_pattern])

    where_sql = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""

    # Count total
    count_row = db.fetch_one("SELECT count(*) as total FROM member" + where_sql, params)
    total_records = count_row.get("total", 0) if count_row else 0
    total_pages = (total_records + limit - 1) // limit

    # Get records
    members_res = db.fetch(
        f"SELECT * FROM member {where_sql} ORDER BY id DESC LIMIT ? OFFSET ?",
        params + [limit, offset]
    )
    members = members_res.records

    return response({
        "members": members,
        "pagination": {
            "current_page": page,
            "limit": limit,
            "total_records": total_records,
            "total_pages": total_pages
        }
    })

@get("/api/members/{id:int}")
async def get_member(id, request, response):
    staff = get_current_staff(request)
    if not staff:
        return response({"error": "Unauthorized", "message": "Valid staff session or token required"}, 401)

    db = ORM._get_db()
    member = db.fetch_one("SELECT * FROM member WHERE id = ?", [id])
    if not member:
        return response({"error": "Not Found", "message": f"Member with ID {id} not found"}, 404)

    return response(member)

@post("/api/members")
async def create_member(request, response):
    staff = get_current_staff(request)
    if not staff:
        return response({"error": "Unauthorized", "message": "Valid staff session or token required"}, 401)

    body = request.body or {}
    name = body.get("name", "").strip()
    email = body.get("email", "").strip()

    # Validate
    errors = []
    if not name:
        errors.append("Name is required")
    if not email:
        errors.append("Email is required")
    elif not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        errors.append("Email is invalid")

    db = ORM._get_db()
    if email:
        existing = db.fetch_one("SELECT id FROM member WHERE email = ?", [email])
        if existing:
            errors.append("Email already registered")

    if errors:
        return response({"error": "Validation Error", "message": "; ".join(errors)}, 400)

    # Insert member
    now_str = datetime.now().strftime("%Y-%m-%d")
    db.execute(
        "INSERT INTO member (name, email, join_date) VALUES (?, ?, ?)",
        [name, email, now_str]
    )
    db.commit()

    new_member = db.fetch_one("SELECT * FROM member WHERE email = ?", [email])
    member_id = new_member["id"] if new_member else 0

    # Log action
    log_change(staff["staff_id"], "add_member", "member", member_id, {
        "name": name,
        "email": email,
        "join_date": now_str
    })

    return response({"message": "Member added successfully", "member_id": member_id}, 201)

@put("/api/members/{id:int}")
@post("/api/members/{id:int}")
async def update_member(id, request, response):
    staff = get_current_staff(request)
    if not staff:
        return response({"error": "Unauthorized", "message": "Valid staff session or token required"}, 401)

    db = ORM._get_db()
    member = db.fetch_one("SELECT * FROM member WHERE id = ?", [id])
    if not member:
        return response({"error": "Not Found", "message": f"Member with ID {id} not found"}, 404)

    body = request.body or {}
    name = body.get("name", "").strip()
    email = body.get("email", "").strip()

    # Validate
    errors = []
    if not name:
        errors.append("Name is required")
    if not email:
        errors.append("Email is required")
    elif not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        errors.append("Email is invalid")

    if email and email != member["email"]:
        existing = db.fetch_one("SELECT id FROM member WHERE email = ?", [email])
        if existing:
            errors.append("Email already registered")

    if errors:
        return response({"error": "Validation Error", "message": "; ".join(errors)}, 400)

    # Update member
    db.execute(
        "UPDATE member SET name = ?, email = ? WHERE id = ?",
        [name, email, id]
    )
    db.commit()

    # Log action
    log_change(staff["staff_id"], "edit_member", "member", id, {
        "name": name,
        "email": email
    })

    return response({"message": "Member updated successfully"})

@delete("/api/members/{id:int}")
async def delete_member_endpoint(id, request, response):
    staff = get_current_staff(request)
    if not staff:
        return response({"error": "Unauthorized", "message": "Valid staff session or token required"}, 401)

    db = ORM._get_db()
    member = db.fetch_one("SELECT * FROM member WHERE id = ?", [id])
    if not member:
        return response({"error": "Not Found", "message": f"Member with ID {id} not found"}, 404)

    # Check if there are active loans
    active_loan = db.fetch_one("SELECT id FROM loan WHERE member_id = ? AND returned = 0", [id])
    if active_loan:
        return response({"error": "Conflict", "message": "Cannot delete a member with active book loans"}, 409)

    # Delete member and their loan history
    db.execute("DELETE FROM member WHERE id = ?", [id])
    db.execute("DELETE FROM loan WHERE member_id = ?", [id])
    db.commit()

    # Log action
    log_change(staff["staff_id"], "remove_member", "member", id, {
        "name": member["name"],
        "email": member["email"]
    })

    return response({"message": "Member deleted successfully"})
