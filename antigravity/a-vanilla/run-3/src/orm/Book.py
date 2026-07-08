from tina4_python import ORM, IntegerField, StringField

class Book(ORM):
    table_name = "books"
    id = IntegerField(primary_key=True, auto_increment=True)
    title = StringField()
    author = StringField()
    published_year = IntegerField()
    isbn = StringField()
    cover_image = StringField()
