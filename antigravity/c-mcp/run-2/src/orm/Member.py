from tina4_python.orm import ORM, IntegerField, StringField

class Member(ORM):
    table_name = "members"
    id = IntegerField(primary_key=True, auto_increment=True)
    name = StringField(required=True)
    email = StringField(required=True)
    join_date = StringField(required=True)
