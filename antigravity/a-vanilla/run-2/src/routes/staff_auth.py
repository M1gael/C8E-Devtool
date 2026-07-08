from tina4_python.core.router import post, noauth
from tina4_python.auth import Auth
from src.orm.staff import Staff

class StaffAuthMiddleware:
    @staticmethod
    def before_auth(request, response):
        # Check Authorization header first
        token = None
        auth_header = ""
        if hasattr(request, "headers") and isinstance(request.headers, dict):
            auth_header = request.headers.get("authorization", request.headers.get("Authorization", ""))
        elif hasattr(request, "headers") and hasattr(request.headers, "get"):
            auth_header = request.headers.get("authorization", "")
            
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]
        
        # Fallback to session token
        if not token and hasattr(request, "session") and request.session:
            token = request.session.get("token")
            
        if not token:
            if hasattr(request, "path") and request.path.startswith("/api/"):
                return request, response.json({"error": "Unauthorized. Staff login required."}, 401)
            else:
                return request, response.redirect("/login")
                
        payload = Auth.valid_token(token)
        if payload is None:
            if hasattr(request, "path") and request.path.startswith("/api/"):
                return request, response.json({"error": "Session expired or invalid token."}, 401)
            else:
                return request, response.redirect("/login")
                
        request.params["user"] = payload
        return request, response

@post("/api/staff/login")
@noauth()
async def staff_login(request, response):
    body = request.body
    if not body or not body.get("email") or not body.get("password"):
        return response.json({"error": "Email and password are required."}, 400)
        
    staffs = Staff.where("email = ?", [body["email"]])
    if not staffs:
        return response.json({"error": "Invalid email or password."}, 401)
        
    staff = staffs[0]
    if not staff.verify_password(body["password"]):
        return response.json({"error": "Invalid email or password."}, 401)
        
    token = Auth.get_token({
        "staff_id": staff.id,
        "name": staff.name,
        "email": staff.email
    })
    
    if request.session:
        request.session.set("token", token)
        request.session.set("user", {
            "id": staff.id,
            "name": staff.name,
            "email": staff.email
        })
        
    return response.json({
        "message": "Login successful.",
        "token": token,
        "user": staff.safe_dict()
    })

@post("/api/staff/logout")
@noauth()
async def staff_logout(request, response):
    if request.session:
        request.session.delete("token")
        request.session.delete("user")
        
    return response.json({"message": "Logout successful."})
