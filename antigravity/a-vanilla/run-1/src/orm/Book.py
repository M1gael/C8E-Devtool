from tina4_python import ORM, IntegerField, StringField, TextField

class Book(ORM):
    id = IntegerField(primary_key=True, auto_increment=True)
    title = StringField()
    author = StringField()
    published_year = IntegerField()
    isbn = StringField()
    cover_image = TextField()
