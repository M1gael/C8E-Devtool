from tina4_python.orm import ORM, IntegerField, StringField

class Staff(ORM):
    table_name = "staff"
    id = IntegerField(primary_key=True, auto_increment=True)
    name = StringField(required=True)
    email = StringField(required=True)
    password_hash = StringField(required=True)
