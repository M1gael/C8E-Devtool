import os
from tina4_python.auth import Auth
from tina4_python.database import Database

def get_logged_in_staff(request):
    """
    Extracts and validates the logged-in staff member from a request.
    Checks Authorization Header, formToken body parameter, or Session cookie.
    """
    token = None
    
    # 1. Check Authorization header
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        
    # 2. Check form token in body (used by AJAX submissions)
    if not token:
        body = getattr(request, "body", None) or {}
        if isinstance(body, dict):
            token = body.get("formToken")
            
    # 3. Check session
    if not token:
        session = getattr(request, "session", None)
        if session:
            token = session.get("token")
            
    if not token:
        return None
        
    # Validate the token
    payload = Auth.valid_token_static(token)
    if payload and "staff_id" in payload:
        return payload
        
    return None

def log_audit(staff_id, action, target_type, target_id, description):
    """
    Record an action performed by a staff member to the audit_logs table.
    """
    db = Database()
    db.insert("audit_logs", {
        "staff_id": staff_id,
        "action": action,
        "target_type": target_type,
        "target_id": target_id,
        "description": description
    })
