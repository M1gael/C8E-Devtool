from tina4_python.orm import ORM, IntegerField, StringField, ForeignKeyField
from src.orm.Book import Book
from src.orm.Member import Member
from src.orm.User import User

class Loan(ORM):
    table_name = "loans"
    id = IntegerField(primary_key=True, auto_increment=True)
    book_id = ForeignKeyField(to=Book, related_name="loans")
    member_id = ForeignKeyField(to=Member, related_name="loans")
    borrow_date = StringField()
    due_date = StringField()
    returned = IntegerField()
    returned_date = StringField()
    staff_id = ForeignKeyField(to=User, related_name="loans")
