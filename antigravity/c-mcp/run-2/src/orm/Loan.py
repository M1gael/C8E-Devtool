from tina4_python.orm import ORM, IntegerField, StringField, ForeignKeyField
from src.orm.Book import Book
from src.orm.Member import Member

class Loan(ORM):
    table_name = "loans"
    id = IntegerField(primary_key=True, auto_increment=True)
    book_id = ForeignKeyField(to=Book, related_name="loans")
    member_id = ForeignKeyField(to=Member, related_name="loans")
    borrow_date = StringField(required=True)
    due_date = StringField(required=True)
    returned = IntegerField(default=0) # 0 = borrowed/active, 1 = returned
