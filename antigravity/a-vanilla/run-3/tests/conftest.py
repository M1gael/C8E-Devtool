import os
import pytest
from tina4_python.database.connection import Database
from tina4_python import bind_database
from tina4_python.migration import migrate

@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    # Force sqlite test database
    os.environ["TINA4_DATABASE_URL"] = "sqlite:///data/test.db"
    
    # Ensure data directory exists
    os.makedirs("data", exist_ok=True)
    
    # Initialize connection and bind globally
    db = Database("sqlite:///data/test.db")
    bind_database(db)
    
    # Run migrations
    migrate(db)
    
    # Import routes to register them with the router
    import src.routes.api
    import src.routes.web
