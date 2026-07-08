import json
from src.orm.AuditLog import AuditLog

def log_change(user_id: int, action: str, details: dict | str):
    """Inserts an audit log entry attributing the action to the staff member.
    
    Args:
        user_id: ID of the staff member (User) performing the action
        action: String descriptor of the action (e.g., 'ADD_BOOK')
        details: Dict or string containing detailed changes or record identifier
    """
    try:
        details_str = json.dumps(details) if isinstance(details, dict) else str(details)
        log_entry = AuditLog(
            user_id=user_id,
            action=action,
            details=details_str
        )
        log_entry.save()
    except Exception as e:
        print(f"Failed to write audit log: {e}")
