import json
from tina4_python.orm import ORM, IntegerField, StringField

class AuditLog(ORM):
    table_name = "audit_logs"

    id = IntegerField(primary_key=True, auto_increment=True)
    staff_id = IntegerField(required=True)
    action = StringField(required=True, max_length=100)
    details = StringField(required=True)

    @staticmethod
    def log(staff_id, action, details_dict):
        log_entry = AuditLog()
        log_entry.staff_id = staff_id
        log_entry.action = action
        log_entry.details = json.dumps(details_dict)
        log_entry.save()
        return log_entry
