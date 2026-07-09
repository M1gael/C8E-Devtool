from tina4_python import ORM, IntegerField, StringField, ForeignKeyField
from src.orm.Staff import Staff

class AuditLog(ORM):
    table_name = "audit_logs"
    
    id = IntegerField(primary_key=True, auto_increment=True)
    staff_id = ForeignKeyField(to=Staff, related_name="audit_logs")
    action = StringField()
    target_type = StringField()
    target_id = IntegerField()
    description = StringField()
