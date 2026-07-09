import os
import unittest
import shutil
from datetime import datetime, timedelta

# Force database to be test.db for test isolation
os.environ["TINA4_DATABASE_URL"] = "sqlite:///test.db"

# Import routing modules so decorators run and register routes
import src.routes.web
import src.routes.api
import app

from tina4_python.database import Database
from tina4_python.migration import migrate
from tina4_python.test_client import TestClient
from tina4_python.queue import Queue
from tina4_python.auth import Auth

class TestLendApp(unittest.TestCase):
    db = None
    client = None
    token = None
    book_id = None
    member_id = None
    loan_id = None

    @classmethod
    def setUpClass(cls):
        # Remove existing test.db to ensure clean slate
        if os.path.exists("test.db"):
            try:
                os.remove("test.db")
            except OSError:
                pass
        
        # Clear uploads folder in test if any
        if os.path.exists(os.path.join("src", "public", "uploads", "cover_images")):
            shutil.rmtree(os.path.join("src", "public", "uploads", "cover_images"), ignore_errors=True)

        cls.db = Database()
        
        # Explicitly drop all tables to clear state on locked databases
        for table in ["audit_logs", "loans", "members", "books", "staff", "tina4_migration"]:
            try:
                cls.db.execute(f"DROP TABLE IF EXISTS {table}")
            except Exception:
                pass
                
        # Run migrations to build the tables and seed default admin
        migrate(cls.db)
        cls.client = TestClient()

    @classmethod
    def tearDownClass(cls):
        # Clean up database
        if os.path.exists("test.db"):
            try:
                os.remove("test.db")
            except OSError:
                pass

    def test_01_migrations_and_seed(self):
        # Check if tables exist and default admin is seeded
        admin = self.db.fetch_one("SELECT * FROM staff WHERE username = ?", ["admin"])
        self.assertIsNotNone(admin)
        self.assertEqual(admin["email"], "admin@lend.local")
        self.assertTrue(Auth.check_password("admin123", admin["password_hash"]))

    def test_02_public_endpoints(self):
        # Public catalogue web view
        response = self.client.get("/")
        self.assertEqual(response.status, 200)
        self.assertIn("Lend", response.text())
        
        # Public catalogue JSON API
        response = self.client.get("/api/books")
        self.assertEqual(response.status, 200)
        body = response.json()
        self.assertIn("books", body)
        self.assertIn("pagination", body)

    def test_03_login_validation(self):
        # Login with invalid credentials
        response = self.client.post("/api/login", json={"username": "admin", "password": "wrongpassword"})
        self.assertEqual(response.status, 401)
        self.assertIn("error", response.json())
        
        # Login with valid credentials
        response = self.client.post("/api/login", json={"username": "admin", "password": "admin123"})
        self.assertEqual(response.status, 200)
        body = response.json()
        self.assertIn("token", body)
        self.assertIn("username", body)
        TestLendApp.token = body["token"]

    def test_04_unauthorized_endpoints(self):
        # Try to access secured routes without token
        response = self.client.post("/api/books", json={"title": "Unauthorized Book"})
        self.assertEqual(response.status, 401)

        response = self.client.post("/api/members", json={"name": "Unauthorized Member"})
        self.assertEqual(response.status, 401)

        response = self.client.post("/api/loans", json={"book_id": 1, "member_id": 1})
        self.assertEqual(response.status, 401)

    def test_05_books_crud(self):
        headers = {"Authorization": f"Bearer {self.token}"}
        
        # Add book
        book_data = {
            "title": "Clean Code",
            "author": "Robert C. Martin",
            "published_year": 2008,
            "isbn": "978-0132350884"
        }
        response = self.client.post("/api/books", json=book_data, headers=headers)
        self.assertEqual(response.status, 201)
        body = response.json()
        self.assertEqual(body["title"], "Clean Code")
        TestLendApp.book_id = body["id"]

        # Edit book
        edit_data = {
            "title": "Clean Code (Updated Title)",
            "author": "Robert C. Martin",
            "published_year": 2008,
            "isbn": "978-0132350884"
        }
        response = self.client.put(f"/api/books/{self.book_id}", json=edit_data, headers=headers)
        self.assertEqual(response.status, 200)
        self.assertEqual(response.json()["title"], "Clean Code (Updated Title)")

    def test_06_members_crud(self):
        headers = {"Authorization": f"Bearer {self.token}"}
        
        # Add member
        member_data = {
            "name": "Jane Doe",
            "email": "jane@example.com",
            "join_date": "2026-07-09"
        }
        response = self.client.post("/api/members", json=member_data, headers=headers)
        self.assertEqual(response.status, 201)
        body = response.json()
        self.assertEqual(body["name"], "Jane Doe")
        TestLendApp.member_id = body["id"]

    def test_07_borrowing_constraints(self):
        headers = {"Authorization": f"Bearer {self.token}"}
        due_date = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")
        
        # Record a loan
        loan_data = {
            "book_id": self.book_id,
            "member_id": self.member_id,
            "due_date": due_date
        }
        response = self.client.post("/api/loans", json=loan_data, headers=headers)
        self.assertEqual(response.status, 201)
        body = response.json()
        self.assertEqual(body["book_id"], self.book_id)
        TestLendApp.loan_id = body["id"]

        # Verify book status in catalogue is unavailable
        response = self.client.get(f"/api/books/{self.book_id}")
        self.assertEqual(response.status, 200)
        self.assertFalse(response.json()["book"]["is_available"])

        # Check queue topic 'emails' has been populated
        q = Queue(topic="emails")
        self.assertGreater(q.size(), 0)

        # Attempt to borrow already borrowed book (double booking rejection)
        response = self.client.post("/api/loans", json=loan_data, headers=headers)
        self.assertEqual(response.status, 409)
        self.assertIn("already out on loan", response.json()["message"])

        # Return the book
        response = self.client.post(f"/api/loans/return/{self.loan_id}", headers=headers)
        self.assertEqual(response.status, 200)

        # Verify book status is now available
        response = self.client.get(f"/api/books/{self.book_id}")
        self.assertEqual(response.status, 200)
        self.assertTrue(response.json()["book"]["is_available"])

    def test_08_audit_logs(self):
        headers = {"Authorization": f"Bearer {self.token}"}
        
        # Retrieve logs
        response = self.client.get("/api/audit-logs", headers=headers)
        self.assertEqual(response.status, 200)
        body = response.json()
        self.assertGreater(len(body), 0)
        
        # Verify first action was recording return or borrow
        self.assertEqual(body[0]["username"], "admin")
        self.assertIn("RETURN", body[0]["action"])
