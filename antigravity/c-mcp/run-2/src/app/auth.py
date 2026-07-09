from tina4_python.auth import valid_token
from src.orm.Staff import Staff

def get_authenticated_staff(request):
    """
    Validates staff credentials via Bearer JWT token or Web Session.
    Returns the Staff instance if valid, or None if unauthenticated.
    """
    # Check 1: Authorization Bearer header (for API)
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        payload = valid_token(token)
        if payload and "staff_id" in payload:
            staff_id = payload["staff_id"]
            staff = Staff()
            if staff.load("id = ?", [staff_id]):
                return staff

    # Check 2: Session cookie (for Web Interface)
    if hasattr(request, "session") and request.session:
        staff_id = request.session.get("staff_id")
        if staff_id:
            staff = Staff()
            if staff.load("id = ?", [staff_id]):
                return staff

    return None
