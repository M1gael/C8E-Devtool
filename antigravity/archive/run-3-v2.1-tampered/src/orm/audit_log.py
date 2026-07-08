from tina4_python.orm import ORM, IntegerField, StringField, TextField, belongs_to

class AuditLog(ORM):
    table_name = "audit_logs"

    id = IntegerField(primary_key=True, auto_increment=True)
    staff_id = IntegerField()
    action = StringField(required=True)
    target_id = IntegerField()
    details = TextField()
    created_at = StringField()

    staff = belongs_to("Staff", foreign_key="staff_id")
