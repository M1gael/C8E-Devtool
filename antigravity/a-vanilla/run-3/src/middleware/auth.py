from tina4_python.auth import Auth

async def get_auth_user(request, response=None):
    # If already set
    if "user" in request.params and request.params["user"]:
        return request.params["user"]

    # Fetch token from header or cookie
    auth_header = request.headers.get("authorization", "")
    token = None
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]
    else:
        token = request.cookies.get("token")

    payload = None
    if token:
        payload = Auth.valid_token(token)

    # Alternatively check session (for browser-based staff actions)
    staff_id = request.session.get("staff_id") if (hasattr(request, "session") and request.session) else None
    
    if payload is None and staff_id is not None:
        from src.orm.staff import Staff
        staff = Staff.find_by_id(staff_id)
        if staff:
            payload = {
                "staff_id": staff.id,
                "email": staff.email,
                "name": staff.name
            }

    if payload:
        request.params["user"] = payload
        return payload
        
    return None

async def auth_middleware(request, response, next_handler):
    user = await get_auth_user(request, response)
    if not user:
        accept_header = request.headers.get("accept", "")
        # If it's an API request or a path starting with /api, return 401 JSON
        if "application/json" in accept_header or request.path.startswith("/api"):
            return response.json({"error": "Unauthorized. Staff sign-in required."}, 401)
        # If it's a web request, redirect to login page
        return response.redirect("/login")

    return await next_handler(request, response)
