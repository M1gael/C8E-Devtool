from tina4_python.core import run
from tina4_python.database import Database
from tina4_python.orm import bind_database

# Initialize database connection and bind it to the Active Record ORM
db = Database()
bind_database(db)

# Import routes to make sure they are registered/discovered
import example.routes
import example.models

if __name__ == "__main__":
    print("Starting example Tina4 application...")
    run()
