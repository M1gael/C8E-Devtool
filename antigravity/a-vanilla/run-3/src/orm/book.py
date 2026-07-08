from tina4_python.orm import ORM, IntegerField, StringField, has_many

class Book(ORM):
    table_name = "books"

    id = IntegerField(primary_key=True, auto_increment=True)
    title = StringField(required=True)
    author = StringField(required=True)
    published_year = IntegerField(required=True)
    isbn = StringField(required=True)
    cover_image = StringField(default="")

    # Relationship
    loans = has_many("Loan", foreign_key="book_id")

    @property
    def is_available(self) -> bool:
        from src.orm.loan import Loan
        active_loans = Loan.where("book_id = ? AND returned = 0", [self.id])
        return len(active_loans) == 0

    @property
    def active_loan(self):
        from src.orm.loan import Loan
        active_loans = Loan.where("book_id = ? AND returned = 0", [self.id])
        return active_loans[0] if active_loans else None
