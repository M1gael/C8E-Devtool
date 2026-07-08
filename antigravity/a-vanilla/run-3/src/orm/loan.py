from tina4_python.orm import ORM, IntegerField, StringField, belongs_to

class Loan(ORM):
    table_name = "loans"

    id = IntegerField(primary_key=True, auto_increment=True)
    book_id = IntegerField(required=True)
    member_id = IntegerField(required=True)
    borrow_date = StringField(required=True)
    due_date = StringField(required=True)
    returned = IntegerField(default=0)  # 0 = active/borrowed, 1 = returned
    returned_date = StringField()

    # Relationships
    book = belongs_to("Book", foreign_key="book_id")
    member = belongs_to("Member", foreign_key="member_id")
