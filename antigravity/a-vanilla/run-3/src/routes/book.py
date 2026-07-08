from tina4_python import get, post, put, delete


@get("/book")
async def get_list(request, response):
    """List all."""
    return response.json({"data": []})


@get("/book/{id}")
async def get_one(request, response):
    """Get by id."""
    return response.json({"data": {}})


@post("/book")
async def create(request, response):
    """Create new."""
    return response.json({"message": "created"}, 201)


@put("/book/{id}")
async def update(request, response):
    """Update by id."""
    return response.json({"message": "updated"})


@delete("/book/{id}")
async def remove(request, response):
    """Delete by id."""
    return response.json({"message": "deleted"})
