from tina4_python.core.router import get, post, noauth
from tina4_python.database import Database
from example.models import User

@get("/api/example/users")
async def list_users(request, response):
    """
    Get a list of all users from the database.
    """
    db = Database()
    users_result = db.fetch("SELECT * FROM users")
    users = users_result.to_array() if users_result else []
    return response({"users": users})

@post("/api/example/users")
@noauth()
async def create_user(request, response):
    """
    Create a new user using the User ORM model.
    """
    name = request.body.get("name")
    email = request.body.get("email")
    if not name:
        return response({"error": "Name is required"}, 400)
    
    # Instantiate and save the user using Tina4 ORM
    user = User(name=name, email=email)
    if user.save():
        return response({
            "message": "User created successfully",
            "user": {
                "id": user.id,
                "name": user.name,
                "email": user.email
            }
        }, 201)
    
    return response({"error": "Failed to save user"}, 500)
