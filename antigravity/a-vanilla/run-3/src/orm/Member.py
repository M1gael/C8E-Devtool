from tina4_python import ORM, IntegerField, StringField

class Member(ORM):
    table_name = "members"
    id = IntegerField(primary_key=True, auto_increment=True)
    name = StringField()
    email = StringField()
    join_date = StringField()
