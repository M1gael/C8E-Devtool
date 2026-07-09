from tina4_python.orm import ORM, IntegerField, StringField

class User(ORM):
    """
    User ORM model mapping to the 'users' table.
    Uses Tina4 Active Record ORM.
    """
    table_name = "users"
    id = IntegerField(primary_key=True, auto_increment=True)
    name = StringField(required=True)
    email = StringField()
