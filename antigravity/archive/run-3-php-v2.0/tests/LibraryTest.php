<?php

use PHPUnit\Framework\TestCase;
use Tina4\TestClient;
use Tina4\Queue;

class LibraryTest extends TestCase
{
    private static ?TestClient $client = null;
    private static ?string $token = null;
    private static ?int $testBookId = null;
    private static ?int $testMemberId = null;

    public static function setUpBeforeClass(): void
    {
        self::$client = new TestClient();
    }

    /**
     * Test public catalog browsing and search
     */
    public function testPublicCatalog()
    {
        // Get all books
        $response = self::$client->get("/api/books");
        $this->assertEquals(200, $response->status, "Browse books should return 200 OK");
        
        $body = $response->json();
        $this->assertNotNull($body["books"], "Response should contain books array");
        $this->assertTrue($body["count"] >= 5, "Initial catalog should contain at least 5 seeded books");

        // Search for a specific book
        $response = self::$client->get("/api/books?search=Hobbit");
        $this->assertEquals(200, $response->status, "Search books should return 200 OK");
        
        $body = $response->json();
        $this->assertEquals(1, $body["count"], "Search count for 'Hobbit' should be 1");
        $this->assertEquals("The Hobbit", $body["books"][0]["title"], "First book title should be 'The Hobbit'");
        $this->assertTrue($body["books"][0]["available"], "The Hobbit should be available initially");

        // View single book details
        $response = self::$client->get("/api/books/1");
        $this->assertEquals(200, $response->status, "View book details should return 200 OK");
        $body = $response->json();
        $this->assertEquals("The Hobbit", $body["title"], "Book details title should match");
        $this->assertTrue($body["available"], "Book should report availability");
    }

    /**
     * Test authentication guard rejects unauthorized actions
     */
    public function testAuthRejection()
    {
        // Try to add a book without token
        $response = self::$client->post("/api/books", json: [
            "title" => "Unauthorized Book",
            "author" => "No Name",
            "published_year" => 2026,
            "isbn" => "1111111111"
        ]);
        $this->assertEquals(401, $response->status, "Anonymous book addition should return 401 Unauthorized");

        // Try to add a member without token
        $response = self::$client->post("/api/members", json: [
            "name" => "Unauthorized Member",
            "email" => "no@auth.com",
            "join_date" => "2026-07-08"
        ]);
        $this->assertEquals(401, $response->status, "Anonymous member registration should return 401");

        // Try to record a loan without token
        $response = self::$client->post("/api/loans", json: [
            "book_id" => 1,
            "member_id" => 1,
            "borrow_date" => "2026-07-08",
            "due_date" => "2026-07-22"
        ]);
        $this->assertEquals(401, $response->status, "Anonymous loan recording should return 401");
    }

    /**
     * Test staff sign in
     */
    public function testStaffLogin()
    {
        // Invalid credentials
        $response = self::$client->post("/api/auth/login", json: [
            "email" => "staff@library.com",
            "password" => "wrong-password"
        ]);
        $this->assertEquals(401, $response->status, "Invalid password login should return 401");

        // Valid credentials (seeded in migrations)
        $response = self::$client->post("/api/auth/login", json: [
            "email" => "staff@library.com",
            "password" => "password123"
        ]);
        $this->assertEquals(200, $response->status, "Valid login should return 200 OK");
        
        $body = $response->json();
        $this->assertNotNull($body["token"], "Login response must contain a token");
        $this->assertEquals("staff@library.com", $body["user"]["email"], "User email must match");
        
        self::$token = $body["token"];
    }

    /**
     * Test authenticated staff actions (Adding book, registering member)
     */
    public function testStaffActions()
    {
        $headers = ["Authorization" => "Bearer " . self::$token];

        // 1. Add Book
        $isbn = "9780593135204";
        $response = self::$client->post("/api/books", json: [
            "title" => "Project Hail Mary",
            "author" => "Andy Weir",
            "published_year" => 2021,
            "isbn" => $isbn,
            "cover_image" => "/images/default_cover.jpg"
        ], headers: $headers);

        $this->assertEquals(201, $response->status, "Staff should add book successfully");
        $body = $response->json();
        $this->assertNotNull($body["id"], "Added book should have an ID");
        self::$testBookId = $body["id"];

        // 2. Add Member
        $response = self::$client->post("/api/members", json: [
            "name" => "Dave Bowman",
            "email" => "dave@discovery.com",
            "join_date" => "2026-07-08"
        ], headers: $headers);

        $this->assertEquals(201, $response->status, "Staff should register member successfully");
        $body = $response->json();
        $this->assertNotNull($body["id"], "Added member should have an ID");
        self::$testMemberId = $body["id"];
    }

    /**
     * Test borrowing constraint logic and async queueing
     */
    public function testBorrowingAndReturn()
    {
        $headers = ["Authorization" => "Bearer " . self::$token];
        
        // Count initial queue size
        $queue = new Queue(topic: 'emails');
        $initialQueueSize = $queue->size('pending');

        // 1. Record Loan
        $response = self::$client->post("/api/loans", json: [
            "book_id" => self::$testBookId,
            "member_id" => self::$testMemberId,
            "borrow_date" => "2026-07-08",
            "due_date" => "2026-07-22"
        ], headers: $headers);

        $this->assertEquals(201, $response->status, "Loan should be recorded successfully");
        
        // 2. Validate Book Availability Status
        $response = self::$client->get("/api/books/" . self::$testBookId);
        $body = $response->json();
        $this->assertFalse($body["available"], "Book should be marked NOT available after loan");

        // 3. Verify Async Queueing
        $newQueueSize = $queue->size('pending');
        $this->assertEquals($initialQueueSize + 1, $newQueueSize, "Queue pending count should increase by 1");

        // 4. Reject borrowing of an already borrowed book
        $response = self::$client->post("/api/loans", json: [
            "book_id" => self::$testBookId,
            "member_id" => self::$testMemberId,
            "borrow_date" => "2026-07-09",
            "due_date" => "2026-07-23"
        ], headers: $headers);
        $this->assertEquals(409, $response->status, "Double borrowing same book should return 409 Conflict");

        // 5. Record Return
        $response = self::$client->post("/api/loans/return", json: [
            "book_id" => self::$testBookId,
            "returned_date" => "2026-07-10"
        ], headers: $headers);
        $this->assertEquals(200, $response->status, "Staff should record return successfully");

        // 6. Validate Book Availability Status Restored
        $response = self::$client->get("/api/books/" . self::$testBookId);
        $body = $response->json();
        $this->assertTrue($body["available"], "Book should be marked available after return");
    }
}
