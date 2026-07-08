from tina4_python.core.router import post, get, noauth
from tina4_python.auth import Auth
from src.orm.Staff import Staff

@noauth()
@post("/api/auth/login")
async def login(request, response):
    body = request.body or {}
    username = body.get("username")
    password = body.get("password")

    is_web_form = "application/x-www-form-urlencoded" in request.content_type

    if not username or not password:
        if is_web_form:
            return response.redirect("/login?error=Username and password are required")
        return response({"error": "Bad Request", "message": "Username and password are required"}, 400)

    # Find staff member
    staff = Staff.select_one("SELECT * FROM staff WHERE username = ?", [username])
    
    if not staff or not Auth.check_password(password, staff.password):
        if is_web_form:
            return response.redirect("/login?error=Invalid username or password")
        return response({"error": "Unauthorized", "message": "Invalid username or password"}, 401)

    # Issue JWT token
    # We will encode staff_id and name in the payload
    payload = {"staff_id": staff.id, "name": staff.name, "username": staff.username}
    token = Auth.get_token_static(payload)

    # If it's a web form, store in session
    if request.session:
        request.session.set("token", token)
        request.session.set("staff_id", staff.id)
        request.session.set("staff_name", staff.name)
        request.session.save()

    if is_web_form:
        return response.redirect("/admin")
        
    return response({
        "token": token,
        "staff": {
            "id": staff.id,
            "username": staff.username,
            "name": staff.name
        },
        "message": "Logged in successfully"
    })

@get("/api/auth/logout")
@post("/api/auth/logout")
@noauth()
async def logout(request, response):
    if request.session:
        request.session.delete("token")
        request.session.delete("staff_id")
        request.session.delete("staff_name")
        request.session.save()

    is_web = "application/x-www-form-urlencoded" in request.content_type or request.method == "GET"
    if is_web:
        return response.redirect("/")
        
    return response({"message": "Logged out successfully"})
