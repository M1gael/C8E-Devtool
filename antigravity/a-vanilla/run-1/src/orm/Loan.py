from tina4_python import ORM, IntegerField, StringField, ForeignKeyField
from src.orm.Book import Book
from src.orm.Member import Member

class Loan(ORM):
    id = IntegerField(primary_key=True, auto_increment=True)
    member_id = ForeignKeyField(to=Member, related_name="loans")
    book_id = ForeignKeyField(to=Book, related_name="loans")
    borrow_date = StringField()
    due_date = StringField()
    returned = IntegerField()  # 0 or 1
    returned_date = StringField()
