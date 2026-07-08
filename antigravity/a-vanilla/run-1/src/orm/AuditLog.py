from tina4_python import ORM, IntegerField, StringField, TextField, ForeignKeyField
from src.orm.Staff import Staff

class AuditLog(ORM):
    id = IntegerField(primary_key=True, auto_increment=True)
    staff_id = ForeignKeyField(to=Staff, related_name="audit_logs")
    action = StringField()
    target_type = StringField()
    target_id = IntegerField()
    details = TextField()
    created_at = StringField()
