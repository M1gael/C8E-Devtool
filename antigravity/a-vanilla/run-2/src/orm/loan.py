from tina4_python.orm import ORM, IntegerField, StringField, belongs_to

class Loan(ORM):
    table_name = "loans"

    id = IntegerField(primary_key=True, auto_increment=True)
    member_id = IntegerField(required=True)
    book_id = IntegerField(required=True)
    borrow_date = StringField(required=True, max_length=10)
    due_date = StringField(required=True, max_length=10)
    returned = IntegerField(default=0)
    return_date = StringField(max_length=10)

    member = belongs_to("Member", foreign_key="member_id")
    book = belongs_to("Book", foreign_key="book_id")
