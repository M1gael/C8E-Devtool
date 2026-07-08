import json
from datetime import datetime
from tina4_python.orm import ORM

def get_current_staff(request):
    """Extract and validate JWT token from header or session."""
    auth_header = request.headers.get("authorization", "")
    token = None
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
    elif request.session:
        token = request.session.get("token")
        
    if not token:
        return None
        
    from tina4_python.auth import Auth
    return Auth.valid_token_static(token)

def log_change(staff_id, action, target_type, target_id, details):
    """Write an event to the library audit log."""
    db = ORM._get_db()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.execute(
        "INSERT INTO audit_log (staff_id, action, target_type, target_id, details, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        [staff_id, action, target_type, target_id, json.dumps(details), now_str]
    )
    db.commit()
