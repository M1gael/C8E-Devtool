from tina4_python.orm import ORM, IntegerField, StringField
from tina4_python.auth import Auth

class Staff(ORM):
    table_name = "staff"

    id = IntegerField(primary_key=True, auto_increment=True)
    name = StringField(required=True)
    email = StringField(required=True)
    password_hash = StringField(required=True)
    created_at = StringField()

    def set_password(self, password: str):
        self.password_hash = Auth.hash_password(password)

    def check_password(self, password: str) -> bool:
        return Auth.check_password(password, self.password_hash)
