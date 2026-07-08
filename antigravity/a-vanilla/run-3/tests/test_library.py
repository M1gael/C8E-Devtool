import os
import unittest
import asyncio
from datetime import date, timedelta

# Set environment variable to use a separate test database before importing Tina4 modules
os.environ["TINA4_DATABASE_URL"] = "sqlite:///data/test_lend.db"
os.environ["TINA4_SECRET"] = "test-secret-key-1234567890-test-secret-key"

from tina4_python.database import Database
from tina4_python.orm import bind_database
from tina4_python.migration import migrate
from tina4_python.auth import Auth
from tina4_python.queue import Queue

# Import ORM models
from src.orm.User import User
from src.orm.Book import Book
from src.orm.Member import Member
from src.orm.Loan import Loan
from src.orm.AuditLog import AuditLog

# Import routes to test
from src.routes.auth import api_login, api_auth_status
from src.routes.catalogue import api_get_catalogue, api_get_book_details
from src.routes.staff_routes import api_add_book, api_add_member, api_add_loan, api_record_return, api_list_audit_logs

# Mock classes for Request/Response/Session
class MockSession:
    def __init__(self, data=None):
        self.data = data or {}
        
    def get(self, key, default=None):
        return self.data.get(key, default)
        
    def set(self, key, value):
        self.data[key] = value
        
    def all(self):
        return self.data
        
    def flash(self, key, value=None):
        return None
        
    def save(self):
        pass
        
    def destroy(self):
        self.data.clear()

class MockRequest:
    def __init__(self, body=None, params=None, headers=None, session=None):
        self.body = body or {}
        self.params = params or {}
        self.headers = {k.lower(): v for k, v in (headers or {}).items()}
        self.session = session or MockSession()

class MockResponse:
    def __init__(self):
        self._status_code = 200
        self._json_body = None
        self._headers = {}
        self._redirect_url = None
        
    def status(self, code):
        self._status_code = code
        return self
        
    def json(self, data, code=200):
        self._status_code = code
        # Mirror Tina4 auto-serialization of domain models
        if hasattr(data, "to_dict"):
            self._json_body = data.to_dict()
        elif isinstance(data, list):
            self._json_body = [item.to_dict() if hasattr(item, "to_dict") else item for item in data]
        else:
            self._json_body = data
        return self
        
    def redirect(self, url):
        self._redirect_url = url
        return self
        
    def header(self, key, value):
        self._headers[key] = value
        return self
        
    def add_header(self, key, value):
        self._headers[key] = value
        return self


class TestLibraryApplication(unittest.IsolatedAsyncioTestCase):
    
    @classmethod
    def setUpClass(cls):
        # Create directories if missing
        os.makedirs("data", exist_ok=True)
        
        # Remove old test database if it exists
        if os.path.exists("data/test_lend.db"):
            try:
                os.remove("data/test_lend.db")
            except OSError:
                pass
                
        # Initialize and bind database
        cls.db = Database()
        bind_database(cls.db)
        
        # Run migrations to setup schema and default staff user
        migrate(cls.db)
        
    def setUp(self):
        # Fetch staff user and generate auth token
        self.staff_user = self.db.fetch_one("SELECT * FROM users WHERE email = 'staff@library.com'")
        self.token = Auth.get_token({"id": self.staff_user["id"], "email": self.staff_user["email"], "name": self.staff_user["name"]})
        self.auth_headers = {"Authorization": f"Bearer {self.token}"}
        
    async def test_01_public_catalogue_empty(self):
        # Query public catalogue
        req = MockRequest()
        res = MockResponse()
        
        await api_get_catalogue(req, res)
        self.assertEqual(res._status_code, 200)
        self.assertEqual(len(res._json_body["books"]), 0)
        self.assertEqual(res._json_body["total"], 0)
        
    async def test_02_auth_guard_refuses_unsigned_in(self):
        # Attempt to add book without auth header
        req = MockRequest(body={"title": "Test Book", "author": "Tester", "published_year": 2026, "isbn": "12345"})
        res = MockResponse()
        
        await api_add_book(req, res)
        # Should return 401 Unauthorized
        self.assertEqual(res._status_code, 401)
        
    async def test_03_staff_actions_add_book_and_member(self):
        # 1. Add Book (authenticated)
        req = MockRequest(
            body={"title": "Clean Code", "author": "Robert C. Martin", "published_year": 2008, "isbn": "978-0132350884"},
            headers=self.auth_headers
        )
        res = MockResponse()
        
        await api_add_book(req, res)
        self.assertEqual(res._status_code, 201)
        self.assertEqual(res._json_body["title"], "Clean Code")
        book_id = res._json_body["id"]
        
        # Verify book exists in database
        book_db = Book.find(book_id)
        self.assertIsNotNone(book_db)
        self.assertEqual(book_db.title, "Clean Code")
        
        # 2. Add Member (authenticated)
        req_member = MockRequest(
            body={"name": "John Doe", "email": "john@example.com"},
            headers=self.auth_headers
        )
        res_member = MockResponse()
        
        await api_add_member(req_member, res_member)
        self.assertEqual(res_member._status_code, 201)
        self.assertEqual(res_member._json_body["name"], "John Doe")
        member_id = res_member._json_body["id"]
        
        # Verify member exists in database
        member_db = Member.find(member_id)
        self.assertIsNotNone(member_db)
        
        # 3. Verify audit log was recorded
        audit_res = self.db.fetch("SELECT * FROM audit_logs WHERE action = 'ADD_BOOK'")
        self.assertEqual(len(audit_res.records), 1)
        self.assertIn("Clean Code", audit_res.records[0]["details"])
        
    async def test_04_loan_and_double_loan_collision(self):
        # Fetch book and member ids
        book = self.db.fetch_one("SELECT * FROM books WHERE title = 'Clean Code'")
        member = self.db.fetch_one("SELECT * FROM members WHERE email = 'john@example.com'")
        
        # Create second member
        member2_req = MockRequest(
            body={"name": "Jane Smith", "email": "jane@example.com"},
            headers=self.auth_headers
        )
        member2_res = MockResponse()
        await api_add_member(member2_req, member2_res)
        member2_id = member2_res._json_body["id"]
        
        # 1. Borrow book for member 1
        due_date = (date.today() + timedelta(days=14)).isoformat()
        loan_req = MockRequest(
            body={"book_id": book["id"], "member_id": member["id"], "due_date": due_date},
            headers=self.auth_headers
        )
        loan_res = MockResponse()
        
        # Clear emails queue folder to verify background email enqueueing
        queue = Queue(topic="emails")
        queue.clear()
        
        await api_add_loan(loan_req, loan_res)
        self.assertEqual(loan_res._status_code, 201)
        loan_id = loan_res._json_body["id"]
        
        # Verify book availability: Should show 0 (borrowed) in details API
        details_req = MockRequest()
        details_res = MockResponse()
        await api_get_book_details(book["id"], details_req, details_res)
        self.assertEqual(details_res._json_body["available"], False)
        
        # 2. Verify receipt email was pushed to queue immediately
        self.assertEqual(queue.size(), 1)
        job = queue.pop()
        self.assertIsNotNone(job)
        self.assertEqual(job.data["member_email"], "john@example.com")
        self.assertEqual(job.data["book_title"], "Clean Code")
        job.complete() # Mark complete
        
        # 3. Attempt to borrow the same book for member 2 (should fail)
        loan2_req = MockRequest(
            body={"book_id": book["id"], "member_id": member2_id, "due_date": due_date},
            headers=self.auth_headers
        )
        loan2_res = MockResponse()
        
        await api_add_loan(loan2_req, loan2_res)
        self.assertEqual(loan2_res._status_code, 400) # Conflict / Bad Request
        self.assertIn("already out on loan", loan2_res._json_body["message"])
        
        # 4. Record return of book
        return_req = MockRequest(headers=self.auth_headers)
        return_res = MockResponse()
        await api_record_return(loan_id, return_req, return_res)
        self.assertEqual(return_res._status_code, 200)
        
        # Verify book is available again
        await api_get_book_details(book["id"], details_req, details_res)
        self.assertEqual(details_res._json_body["available"], True)


if __name__ == "__main__":
    unittest.main()
