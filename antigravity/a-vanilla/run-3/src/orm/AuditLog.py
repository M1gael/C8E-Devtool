from tina4_python.orm import ORM, IntegerField, StringField, ForeignKeyField
from src.orm.User import User

class AuditLog(ORM):
    table_name = "audit_logs"
    id = IntegerField(primary_key=True, auto_increment=True)
    user_id = ForeignKeyField(to=User, related_name="audit_logs")
    action = StringField()
    details = StringField()
    created_at = StringField()
