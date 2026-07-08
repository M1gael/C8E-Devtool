from tina4_python import ORM, IntegerField, StringField

class Staff(ORM):
    id = IntegerField(primary_key=True, auto_increment=True)
    username = StringField()
    password = StringField()
    name = StringField()
