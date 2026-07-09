from tina4_python.orm import ORM, IntegerField, StringField

class Book(ORM):
    table_name = "books"
    id = IntegerField(primary_key=True, auto_increment=True)
    title = StringField(required=True)
    author = StringField(required=True)
    published_year = IntegerField(required=True)
    isbn = StringField(required=True)
    cover_image = StringField()
    is_available = IntegerField(default=1) # 1 = available, 0 = on loan
