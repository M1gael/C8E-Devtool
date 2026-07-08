from tina4_python import ORM, IntegerField, StringField

class User(ORM):
    table_name = "users"
    id = IntegerField(primary_key=True, auto_increment=True)
    name = StringField()
    email = StringField()
    password = StringField()
