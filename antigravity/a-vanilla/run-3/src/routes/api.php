<?php

use Tina4\Router;
use Tina4\Database\Database;
use Tina4\Queue;

/**
 * Helper to log staff actions to the audit trail
 */
function auditLog(int $userId, string $action, string $entityType, int $entityId, array $details = [])
{
    $log = new ActivityLog();
    $log->userId = $userId;
    $log->action = $action;
    $log->entityType = $entityType;
    $log->entityId = $entityId;
    $log->details = json_encode($details);
    $log->save();
}

/**
 * Public book search and listing
 * @noauth
 */
Router::get("/api/books", function ($request, $response) {
    $db = Database::getConnection();

    $search = $request->queryParam("search", "");
    $page = (int) $request->queryParam("page", 1);
    $limit = (int) $request->queryParam("limit", 12);
    if ($page < 1) $page = 1;
    if ($limit < 1) $limit = 12;
    $offset = ($page - 1) * $limit;

    $sql = "SELECT b.*, (SELECT COUNT(*) FROM loans l WHERE l.book_id = b.id AND (l.returned_date IS NULL OR l.returned_date = '')) == 0 AS available FROM books b";
    $countSql = "SELECT COUNT(*) as total FROM books b";
    $params = [];

    if (!empty($search)) {
        $searchCond = " WHERE (b.title LIKE :search OR b.author LIKE :search OR b.published_year LIKE :search OR b.isbn LIKE :search)";
        $sql .= $searchCond;
        $countSql .= $searchCond;
        $params["search"] = "%" . $search . "%";
    }

    $sql .= " ORDER BY b.title ASC LIMIT :limit OFFSET :offset";
    $params["limit"] = $limit;
    $params["offset"] = $offset;

    $books = $db->fetch($sql, $params);
    $totalResult = $db->fetchOne($countSql, ["search" => "%" . $search . "%"]);
    $totalCount = (int) ($totalResult["total"] ?? 0);

    // Convert availability column to boolean
    $records = [];
    foreach ($books as $book) {
        $book["available"] = (bool) $book["available"];
        $book["published_year"] = (int) $book["published_year"];
        $records[] = $book;
    }

    return $response->json([
        "books" => $records,
        "count" => $totalCount,
        "page" => $page,
        "limit" => $limit
    ]);
});

/**
 * Public book details
 * @noauth
 */
Router::get("/api/books/{id:int}", function ($request, $response) {
    $db = Database::getConnection();
    $id = $request->params["id"];

    // Get book
    $book = new Book();
    $book->load("id = ?", [$id]);

    if (empty($book->id)) {
        return $response->json(["error" => "Book not found"], 404);
    }

    // Get availability
    $available = $book->isAvailable();

    // Get loan history
    $loansSql = "SELECT l.id, l.borrow_date, l.due_date, l.returned_date, m.name as member_name, m.email as member_email 
                 FROM loans l 
                 JOIN members m ON l.member_id = m.id 
                 WHERE l.book_id = :book_id 
                 ORDER BY l.borrow_date DESC";
    $loans = $db->fetch($loansSql, ["book_id" => $id]);

    $history = [];
    foreach ($loans as $loan) {
        $history[] = [
            "id" => (int) $loan["id"],
            "member_name" => $loan["member_name"],
            "member_email" => $loan["member_email"],
            "borrow_date" => $loan["borrow_date"],
            "due_date" => $loan["due_date"],
            "returned_date" => $loan["returned_date"] ?: null
        ];
    }

    $data = $book->toDict();
    $data["available"] = $available;
    $data["loans"] = $history;

    return $response->json($data);
});

/**
 * Add a book
 * @noauth
 */
Router::post("/api/books", function ($request, $response) {
    $body = $request->body;
    $staff = $request->user;

    // Validate inputs
    $errors = [];
    if (empty($body["title"])) $errors[] = "Title is required";
    if (empty($body["author"])) $errors[] = "Author is required";
    if (empty($body["published_year"])) {
        $errors[] = "Published year is required";
    } elseif (!is_numeric($body["published_year"])) {
        $errors[] = "Published year must be a number";
    }
    if (empty($body["isbn"])) {
        $errors[] = "ISBN is required";
    }

    if (!empty($errors)) {
        return $response->json(["errors" => $errors], 400);
    }

    // Check unique ISBN
    $existing = new Book();
    $found = $existing->select("SELECT * FROM books WHERE isbn = :isbn", ["isbn" => $body["isbn"]]);
    if (count($found) > 0) {
        return $response->json(["errors" => ["A book with this ISBN already exists"]], 400);
    }

    // Save
    $book = new Book();
    $book->title = trim($body["title"]);
    $book->author = trim($body["author"]);
    $book->publishedYear = (int) $body["published_year"];
    $book->isbn = trim($body["isbn"]);
    $book->coverImage = !empty($body["cover_image"]) ? trim($body["cover_image"]) : "/images/default_cover.jpg";
    $book->save();

    // Log activity
    auditLog($staff["user_id"], "ADD_BOOK", "book", $book->id, $book->toDict());

    return $response->json($book->toDict(), 201);
}, ["authMiddleware"]);

/**
 * Edit a book
 * @noauth
 */
Router::put("/api/books/{id:int}", function ($request, $response) {
    $id = $request->params["id"];
    $body = $request->body;
    $staff = $request->user;

    $book = new Book();
    $book->load("id = ?", [$id]);

    if (empty($book->id)) {
        return $response->json(["error" => "Book not found"], 404);
    }

    // Validate inputs
    $errors = [];
    if (isset($body["published_year"]) && !is_numeric($body["published_year"])) {
        $errors[] = "Published year must be a number";
    }
    if (!empty($errors)) {
        return $response->json(["errors" => $errors], 400);
    }

    // Check ISBN collision
    if (!empty($body["isbn"]) && $body["isbn"] !== $book->isbn) {
        $existing = new Book();
        $found = $existing->select("SELECT * FROM books WHERE isbn = :isbn", ["isbn" => $body["isbn"]]);
        if (count($found) > 0) {
            return $response->json(["errors" => ["A book with this ISBN already exists"]], 400);
        }
        $book->isbn = trim($body["isbn"]);
    }

    $oldData = $book->toDict();

    if (isset($body["title"])) $book->title = trim($body["title"]);
    if (isset($body["author"])) $book->author = trim($body["author"]);
    if (isset($body["published_year"])) $book->publishedYear = (int) $body["published_year"];
    if (isset($body["cover_image"])) $book->coverImage = trim($body["cover_image"]);
    $book->save();

    // Log activity
    auditLog($staff["user_id"], "EDIT_BOOK", "book", $book->id, [
        "before" => $oldData,
        "after" => $book->toDict()
    ]);

    return $response->json($book->toDict());
}, ["authMiddleware"]);

/**
 * Remove a book
 * @noauth
 */
Router::delete("/api/books/{id:int}", function ($request, $response) {
    $id = $request->params["id"];
    $staff = $request->user;

    $book = new Book();
    $book->load("id = ?", [$id]);

    if (empty($book->id)) {
        return $response->json(["error" => "Book not found"], 404);
    }

    $oldData = $book->toDict();
    $book->delete();

    // Log activity
    auditLog($staff["user_id"], "REMOVE_BOOK", "book", $id, $oldData);

    return $response->json(null, 204);
}, ["authMiddleware"]);

/**
 * Get all members
 * @noauth
 */
Router::get("/api/members", function ($request, $response) {
    $members = (new Member())->find([], 0, "name ASC");
    $list = array_map(fn($m) => $m->toDict(), $members);
    return $response->json($list);
}, ["authMiddleware"]);

/**
 * Add a member
 * @noauth
 */
Router::post("/api/members", function ($request, $response) {
    $body = $request->body;
    $staff = $request->user;

    $errors = [];
    if (empty($body["name"])) $errors[] = "Name is required";
    if (empty($body["email"])) {
        $errors[] = "Email is required";
    } elseif (!filter_var($body["email"], FILTER_VALIDATE_EMAIL)) {
        $errors[] = "Invalid email format";
    }
    if (empty($body["join_date"])) $errors[] = "Join date is required";

    if (!empty($errors)) {
        return $response->json(["errors" => $errors], 400);
    }

    // Check unique email
    $existing = new Member();
    $found = $existing->select("SELECT * FROM members WHERE email = :email", ["email" => $body["email"]]);
    if (count($found) > 0) {
        return $response->json(["errors" => ["A member with this email is already registered"]], 400);
    }

    $member = new Member();
    $member->name = trim($body["name"]);
    $member->email = trim($body["email"]);
    $member->joinDate = trim($body["join_date"]);
    $member->save();

    auditLog($staff["user_id"], "ADD_MEMBER", "member", $member->id, $member->toDict());

    return $response->json($member->toDict(), 201);
}, ["authMiddleware"]);

/**
 * Edit a member
 * @noauth
 */
Router::put("/api/members/{id:int}", function ($request, $response) {
    $id = $request->params["id"];
    $body = $request->body;
    $staff = $request->user;

    $member = new Member();
    $member->load("id = ?", [$id]);

    if (empty($member->id)) {
        return $response->json(["error" => "Member not found"], 404);
    }

    $errors = [];
    if (isset($body["email"]) && !filter_var($body["email"], FILTER_VALIDATE_EMAIL)) {
        $errors[] = "Invalid email format";
    }
    if (!empty($errors)) {
        return $response->json(["errors" => $errors], 400);
    }

    // Check email collision
    if (!empty($body["email"]) && $body["email"] !== $member->email) {
        $existing = new Member();
        $found = $existing->select("SELECT * FROM members WHERE email = :email", ["email" => $body["email"]]);
        if (count($found) > 0) {
            return $response->json(["errors" => ["A member with this email is already registered"]], 400);
        }
        $member->email = trim($body["email"]);
    }

    $oldData = $member->toDict();

    if (isset($body["name"])) $member->name = trim($body["name"]);
    if (isset($body["join_date"])) $member->joinDate = trim($body["join_date"]);
    $member->save();

    auditLog($staff["user_id"], "EDIT_MEMBER", "member", $member->id, [
        "before" => $oldData,
        "after" => $member->toDict()
    ]);

    return $response->json($member->toDict());
}, ["authMiddleware"]);

/**
 * Remove a member
 * @noauth
 */
Router::delete("/api/members/{id:int}", function ($request, $response) {
    $id = $request->params["id"];
    $staff = $request->user;

    $member = new Member();
    $member->load("id = ?", [$id]);

    if (empty($member->id)) {
        return $response->json(["error" => "Member not found"], 404);
    }

    $oldData = $member->toDict();
    $member->delete();

    auditLog($staff["user_id"], "REMOVE_MEMBER", "member", $id, $oldData);

    return $response->json(null, 204);
}, ["authMiddleware"]);

/**
 * Record a loan
 * @noauth
 */
Router::post("/api/loans", function ($request, $response) {
    $body = $request->body;
    $staff = $request->user;

    $errors = [];
    if (empty($body["book_id"])) $errors[] = "Book ID is required";
    if (empty($body["member_id"])) $errors[] = "Member ID is required";
    if (empty($body["borrow_date"])) $errors[] = "Borrow date is required";
    if (empty($body["due_date"])) $errors[] = "Due date is required";

    if (!empty($errors)) {
        return $response->json(["errors" => $errors], 400);
    }

    $bookId = (int) $body["book_id"];
    $memberId = (int) $body["member_id"];
    $borrowDate = trim($body["borrow_date"]);
    $dueDate = trim($body["due_date"]);

    // Check Book
    $book = new Book();
    $book->load("id = ?", [$bookId]);
    if (empty($book->id)) {
        return $response->json(["error" => "Book not found"], 404);
    }

    // Check Member
    $member = new Member();
    $member->load("id = ?", [$memberId]);
    if (empty($member->id)) {
        return $response->json(["error" => "Member not found"], 404);
    }

    // Check availability
    if (!$book->isAvailable()) {
        return $response->json(["error" => "This book is already out on loan and cannot be borrowed until it is returned"], 409);
    }

    // Record Loan
    $loan = new Loan();
    $loan->bookId = $bookId;
    $loan->memberId = $memberId;
    $loan->borrowDate = $borrowDate;
    $loan->dueDate = $dueDate;
    $loan->save();

    // Push async email to Queue
    try {
        $queue = new Queue(topic: 'emails');
        $queue->push([
            "to" => $member->email,
            "name" => $member->name,
            "title" => $book->title,
            "borrow_date" => $borrowDate,
            "due_date" => $dueDate
        ]);
    } catch (\Throwable $e) {
        // Log queue failure, but do not crash the loan process
        error_log("Failed to queue email receipt: " . $e->getMessage());
    }

    // Log activity
    auditLog($staff["user_id"], "RECORD_LOAN", "loan", $loan->id, $loan->toDict());

    return $response->json($loan->toDict(), 201);
}, ["authMiddleware"]);

/**
 * Record a book return
 * @noauth
 */
Router::post("/api/loans/return", function ($request, $response) {
    $body = $request->body;
    $staff = $request->user;

    if (empty($body["book_id"])) {
        return $response->json(["error" => "Book ID is required"], 400);
    }

    $bookId = (int) $body["book_id"];
    $returnedDate = !empty($body["returned_date"]) ? trim($body["returned_date"]) : date("Y-m-d");

    // Load active loan
    $loans = (new Loan())->where("book_id = ? AND (returned_date IS NULL OR returned_date = '')", [$bookId]);
    if (count($loans) === 0) {
        return $response->json(["error" => "No active loan found for this book"], 400);
    }

    /** @var Loan $loan */
    $loan = $loans[0];
    $loan->returnedDate = $returnedDate;
    $loan->save();

    // Log activity
    auditLog($staff["user_id"], "RECORD_RETURN", "loan", $loan->id, $loan->toDict());

    return $response->json([
        "message" => "Book returned successfully",
        "loan" => $loan->toDict()
    ]);
}, ["authMiddleware"]);

/**
 * Get audit logs
 * @noauth
 */
Router::get("/api/logs", function ($request, $response) {
    $db = Database::getConnection();

    $sql = "SELECT a.*, u.name as staff_name, u.email as staff_email 
            FROM activity_logs a 
            JOIN users u ON a.user_id = u.id 
            ORDER BY a.created_at DESC LIMIT 100";
    $logs = $db->fetch($sql);

    return $response->json($logs);
}, ["authMiddleware"]);

/**
 * Interactive API documentation endpoints (Swagger / OpenAPI specifications)
 * @noauth
 */
Router::get("/api/docs", function ($request, $response) {
    // Generate simple interactive API documentation summary
    $endpoints = [
        "title" => "Lend Community Library API",
        "version" => "1.0.0",
        "base_path" => "/api",
        "endpoints" => [
            "POST /api/auth/login" => [
                "description" => "Sign in staff user",
                "request" => ["email" => "string", "password" => "string"],
                "response" => ["token" => "string", "user" => "object"]
            ],
            "GET /api/books" => [
                "description" => "Browse and search book catalog",
                "parameters" => ["search" => "string (optional)", "page" => "int", "limit" => "int"],
                "response" => ["books" => "array", "count" => "int", "page" => "int"]
            ],
            "GET /api/books/{id}" => [
                "description" => "Get book details and borrowing history",
                "response" => ["id" => "int", "title" => "string", "available" => "bool", "loans" => "array"]
            ],
            "POST /api/books" => [
                "description" => "Add new book (Staff only)",
                "headers" => ["Authorization" => "Bearer <token>"],
                "request" => ["title" => "string", "author" => "string", "published_year" => "int", "isbn" => "string", "cover_image" => "string"],
                "response" => "Book object"
            ],
            "PUT /api/books/{id}" => [
                "description" => "Edit existing book details (Staff only)",
                "headers" => ["Authorization" => "Bearer <token>"]
            ],
            "DELETE /api/books/{id}" => [
                "description" => "Delete book (Staff only)",
                "headers" => ["Authorization" => "Bearer <token>"]
            ],
            "GET /api/members" => [
                "description" => "Get registered library members (Staff only)",
                "headers" => ["Authorization" => "Bearer <token>"]
            ],
            "POST /api/members" => [
                "description" => "Register new member (Staff only)",
                "headers" => ["Authorization" => "Bearer <token>"],
                "request" => ["name" => "string", "email" => "string", "join_date" => "string"]
            ],
            "POST /api/loans" => [
                "description" => "Record book loan (Staff only)",
                "headers" => ["Authorization" => "Bearer <token>"],
                "request" => ["book_id" => "int", "member_id" => "int", "borrow_date" => "string", "due_date" => "string"]
            ],
            "POST /api/loans/return" => [
                "description" => "Record book return (Staff only)",
                "headers" => ["Authorization" => "Bearer <token>"],
                "request" => ["book_id" => "int", "returned_date" => "string"]
            ],
            "GET /api/logs" => [
                "description" => "Retrieve activity audit logs (Staff only)",
                "headers" => ["Authorization" => "Bearer <token>"]
            ]
        ]
    ];
    return $response->json($endpoints);
});
