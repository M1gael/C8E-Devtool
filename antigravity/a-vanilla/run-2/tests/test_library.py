from tina4_python.test import Test, assert_equal, assert_true, assert_not_none, assert_false
from src.orm.book import Book
from src.orm.member import Member
from src.orm.loan import Loan
from src.orm.staff import Staff
from src.orm.audit_log import AuditLog
from tina4_python.queue import Queue
from tina4_python.database import Database
from tina4_python.orm import bind_database
import json

class LibraryTest(Test):
    
    def set_up(self):
        # Force environment variable to use test database
        import os
        os.environ["TINA4_DATABASE_URL"] = "sqlite:///data/test.db"
        
        db_path = "sqlite:///data/test.db"
        db = Database(db_path)
        bind_database(db)
        
        # Explicitly import all routes so they are registered in the test router context
        import src.routes.staff_auth
        import src.routes.staff_management
        import src.routes.public_catalog
        import src.routes.web_views
        import src.routes.startup
        
        # Create all tables in the test database if they do not exist
        Book.create_table()
        Member.create_table()
        Loan.create_table()
        Staff.create_table()
        AuditLog.create_table()
        
        # Clean all records for test isolation (except Staff which we seed next)
        db.execute("DELETE FROM books")
        db.execute("DELETE FROM members")
        db.execute("DELETE FROM loans")
        db.execute("DELETE FROM audit_logs")
        db.execute("DELETE FROM staff")
        
        # Seed default staff member in test database
        staff = Staff()
        staff.name = "Librarian"
        staff.email = "staff@library.com"
        staff.set_password("password123")
        staff.save()

    def test_01_public_catalog_access(self):
        # 1. Public can search and filter catalog, page through results
        resp = self.get("/api/books")
        assert_equal(resp.status, 200, "Catalog API should be public")
        data = resp.json()
        assert_true("books" in data, "Should return books key")
        assert_true(isinstance(data["books"], list), "books should be a list")
        
    def test_02_unauthenticated_refusal(self):
        # 2. Unauthenticated request to staff APIs are refused with 401
        # e.g. adding a book
        resp = self.post("/api/books", json={"title": "Test Book", "author": "Test Author", "published_year": 2020, "isbn": "1234567890"})
        assert_equal(resp.status, 401, "Adding book without token should fail with 401")
        
        # e.g. borrowing a book
        resp = self.post("/api/loans", json={"book_id": 1, "member_id": 1})
        assert_equal(resp.status, 401, "Recording loan without token should fail with 401")
        
    def test_03_staff_login(self):
        # 3. Staff can authenticate and receive a token
        resp = self.post("/api/staff/login", json={
            "email": "staff@library.com",
            "password": "password123"
        })
        assert_equal(resp.status, 200, "Login should succeed")
        data = resp.json()
        assert_not_none(data.get("token"), "Login response should contain token")
        
    def test_04_book_and_member_creation(self):
        # Login to get token
        login_resp = self.post("/api/staff/login", json={
            "email": "staff@library.com",
            "password": "password123"
        })
        token = login_resp.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Create a book
        resp_book = self.post("/api/books", headers=headers, json={
            "title": "Harry Potter",
            "author": "J.K. Rowling",
            "published_year": 1997,
            "isbn": "9780747532699",
            "cover_image": ""
        })
        assert_equal(resp_book.status, 201, "Should successfully create a book")
        book_id = resp_book.json()["book"]["id"]
        
        # Create a member
        resp_member = self.post("/api/members", headers=headers, json={
            "name": "Jane Doe",
            "email": "jane@example.com"
        })
        assert_equal(resp_member.status, 201, "Should successfully create a member")
        member_id = resp_member.json()["member"]["id"]
        
    def test_05_borrowing_and_constraints(self):
        # Login to get token
        login_resp = self.post("/api/staff/login", json={
            "email": "staff@library.com",
            "password": "password123"
        })
        token = login_resp.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Ensure book and member are seeded
        book = Book()
        book.title = "Harry Potter"
        book.author = "J.K. Rowling"
        book.published_year = 1997
        book.isbn = "9780747532699"
        book.save()
        
        member = Member()
        member.name = "Jane Doe"
        member.email = "jane@example.com"
        member.join_date = "2026-07-08"
        member.save()
        
        # Make sure book is available
        assert_true(book.is_available(), "Book should be available before borrowing")
        
        # Clear queue of emails first to test queue enqueuing
        q = Queue(topic="emails")
        while q.size() > 0:
            q.pop()
            
        # Borrow book
        resp_loan = self.post("/api/loans", headers=headers, json={
            "book_id": book.id,
            "member_id": member.id
        })
        assert_equal(resp_loan.status, 201, "Should successfully record a loan")
        
        # Verify receipt email task is in queue
        assert_true(q.size() > 0, "Receipt email should be queued in background")
        
        # Check availability is now False
        book_reloaded = Book.find_by_id(book.id)
        assert_false(book_reloaded.is_available(), "Book should not be available after borrowing")
        
        # Attempt to borrow again should fail
        resp_double = self.post("/api/loans", headers=headers, json={
            "book_id": book.id,
            "member_id": member.id
        })
        assert_equal(resp_double.status, 400, "Double borrowing should be rejected with 400")
        
    def test_06_return_book(self):
        # Login to get token
        login_resp = self.post("/api/staff/login", json={
            "email": "staff@library.com",
            "password": "password123"
        })
        token = login_resp.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Ensure book and member are seeded and borrowed
        book = Book()
        book.title = "Harry Potter"
        book.author = "J.K. Rowling"
        book.published_year = 1997
        book.isbn = "9780747532699"
        book.save()
        
        member = Member()
        member.name = "Jane Doe"
        member.email = "jane@example.com"
        member.join_date = "2026-07-08"
        member.save()
        
        # Borrow first
        self.post("/api/loans", headers=headers, json={
            "book_id": book.id,
            "member_id": member.id
        })
        
        # Return book
        resp_return = self.post("/api/loans/return", headers=headers, json={
            "book_id": book.id
        })
        assert_equal(resp_return.status, 200, "Should successfully return book")
        
        # Check availability is now True
        book_reloaded = Book.find_by_id(book.id)
        assert_true(book_reloaded.is_available(), "Book should be available after return")
        
    def test_07_audit_logs(self):
        # Login to get token
        login_resp = self.post("/api/staff/login", json={
            "email": "staff@library.com",
            "password": "password123"
        })
        token = login_resp.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Ensure we have a book, member, and record a loan & return to trigger audit logs
        book = Book()
        book.title = "Harry Potter"
        book.author = "J.K. Rowling"
        book.published_year = 1997
        book.isbn = "9780747532699"
        book.save()
        
        member = Member()
        member.name = "Jane Doe"
        member.email = "jane@example.com"
        member.join_date = "2026-07-08"
        member.save()
        
        self.post("/api/loans", headers=headers, json={
            "book_id": book.id,
            "member_id": member.id
        })
        self.post("/api/loans/return", headers=headers, json={
            "book_id": book.id
        })
        
        # Query audit logs
        resp_logs = self.get("/api/audit-logs", headers=headers)
        assert_equal(resp_logs.status, 200, "Should allow viewing audit logs")
        logs = resp_logs.json()
        assert_true(len(logs) > 0, "Audit logs should not be empty")
        
        # Check actions are logged
        actions = [log["action"] for log in logs]
        assert_true("borrow_book" in actions, "borrow_book action should be logged")
        assert_true("return_book" in actions, "return_book action should be logged")
