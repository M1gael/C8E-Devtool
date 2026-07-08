from tina4_python.orm import ORM, IntegerField, StringField

class Book(ORM):
    table_name = "books"

    id = IntegerField(primary_key=True, auto_increment=True)
    title = StringField(required=True, max_length=255)
    author = StringField(required=True, max_length=255)
    published_year = IntegerField(required=True)
    isbn = StringField(required=True, max_length=20)
    cover_image = StringField(max_length=255)

    def is_available(self):
        from src.orm.loan import Loan
        # returned = 0 means borrowed, 1 means returned
        loans = Loan.where("book_id = ? AND returned = 0", [self.id])
        return len(loans) == 0

    def get_history(self):
        from src.orm.loan import Loan
        from src.orm.member import Member
        
        loans = Loan.where("book_id = ? ORDER BY borrow_date DESC", [self.id])
        history = []
        for loan in loans:
            member = Member.find_by_id(loan.member_id)
            history.append({
                "loan": loan.to_dict(),
                "member": member.to_dict() if member else None
            })
        return history
