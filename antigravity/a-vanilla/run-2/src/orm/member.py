from tina4_python.orm import ORM, IntegerField, StringField

class Member(ORM):
    table_name = "members"

    id = IntegerField(primary_key=True, auto_increment=True)
    name = StringField(required=True, max_length=255)
    email = StringField(required=True, max_length=255)
    join_date = StringField(required=True, max_length=10)
