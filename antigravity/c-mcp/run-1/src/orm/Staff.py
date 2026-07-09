from tina4_python import ORM, IntegerField, StringField

class Staff(ORM):
    table_name = "staff"
    
    id = IntegerField(primary_key=True, auto_increment=True)
    username = StringField()
    email = StringField()
    password_hash = StringField()
