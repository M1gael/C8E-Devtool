from tina4_python.orm import ORM, IntegerField, StringField, has_many

class Member(ORM):
    table_name = "members"

    id = IntegerField(primary_key=True, auto_increment=True)
    name = StringField(required=True)
    email = StringField(required=True)
    join_date = StringField(required=True)

    # Relationship
    loans = has_many("Loan", foreign_key="member_id")
