from tina4_python.core.router import get, post, noauth, secured
from tina4_python.auth import Auth
from src.orm.User import User
from src.app.utils import render_template, get_current_user

@noauth()
@get("/login")
async def login_page(request, response):
    """Renders the staff login page."""
    current_user = get_current_user(request)
    if current_user:
        return response.redirect("/staff/dashboard")
    return render_template(request, response, "login.twig")

@noauth()
@post("/api/auth/login")
async def api_login(request, response):
    """Authenticates library staff using email and password."""
    body = request.body or {}
    email = body.get("email")
    password = body.get("password")
    
    if not email or not password:
        return response.json({
            "error": "Bad Request",
            "message": "Email and password are required"
        }, 400)
        
    # Search for user in database
    user = User.load("SELECT * FROM users WHERE email = ?", [email])
    if not user or not Auth.check_password(password, user.password):
        return response.json({
            "error": "Unauthorized",
            "message": "Invalid email or password"
        }, 401)
        
    # User matches, generate JWT token
    token = Auth.get_token({"id": user.id, "email": user.email, "name": user.name})
    
    # Store user and token in session
    request.session.set("user", {"id": user.id, "email": user.email, "name": user.name})
    request.session.set("token", token)
    request.session.save()
    
    # Set session cookie header manually to be secure
    sid = request.session.session_id
    response.header("set-cookie", f"tina4_session={sid}; Path=/; HttpOnly; SameSite=Lax; Max-Age=3600")
    
    return response.json({
        "message": "Login successful",
        "token": token,
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name
        }
    })

@noauth()
@get("/logout")
async def logout_page(request, response):
    """Logs out the user and redirects to the home page."""
    session = getattr(request, "session", None)
    if session:
        session.destroy()
    return response.redirect("/")

@noauth()
@post("/api/auth/logout")
async def api_logout(request, response):
    """Invalidates the staff session."""
    session = getattr(request, "session", None)
    if session:
        session.destroy()
    return response.json({"message": "Logout successful"})

@get("/api/auth/status")
async def api_auth_status(request, response):
    """Returns the profile of the logged-in staff member."""
    current_user = get_current_user(request)
    if not current_user:
        return response.json({
            "error": "Unauthorized",
            "message": "Not signed in"
        }, 401)
    return response.json({"user": current_user})
