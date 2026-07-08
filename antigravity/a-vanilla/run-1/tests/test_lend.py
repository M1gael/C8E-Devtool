import unittest
import subprocess
import time
import urllib.request
import urllib.error
import json
import os
import sys
import shutil
from pathlib import Path

PORT = 7012
BASE_URL = f"http://localhost:{PORT}"

def http_request(path, method="GET", data=None, token=None):
    url = f"{BASE_URL}{path}"
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
        
    req_data = None
    if data is not None:
        req_data = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
        
    req = urllib.request.Request(url, data=req_data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            status = response.status
            body = response.read().decode("utf-8")
            return status, json.loads(body) if body else None
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            res_data = json.loads(body)
        except Exception:
            res_data = body
        return e.code, res_data
    except Exception as e:
        return 0, str(e)

class TestLendApp(unittest.TestCase):
    server_process = None

    @classmethod
    def setUpClass(cls):
        # Ensure data/ directory exists and clean test DB if exists
        test_db = Path("data/lend_test.db")
        if test_db.exists():
            try:
                test_db.unlink()
            except OSError:
                pass
                
        # Clean mailbox directory if exists
        mailbox_dir = Path("data/mailbox")
        if mailbox_dir.exists():
            shutil.rmtree(mailbox_dir, ignore_errors=True)

        # Set environment variables for the test server
        env = os.environ.copy()
        env["TINA4_DATABASE_URL"] = "sqlite:///data/lend_test.db"
        env["PORT"] = str(PORT)
        env["TINA4_DEBUG"] = "true"
        env["TINA4_OVERRIDE_CLIENT"] = "true"
        env["TINA4_AUTO_MIGRATE"] = "true"
        
        # Start server subprocess using the virtual environment python
        python_exe = sys.executable
        cls.server_log_file = open("logs/test_server.log", "w", encoding="utf-8")
        cls.server_process = subprocess.Popen(
            [python_exe, "app.py"],
            env=env,
            stdout=cls.server_log_file,
            stderr=cls.server_log_file
        )
        
        # Wait for server to boot and migrations to run
        time.sleep(4)

    @classmethod
    def tearDownClass(cls):
        if cls.server_process:
            cls.server_process.terminate()
            try:
                cls.server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                cls.server_process.kill()
        if hasattr(cls, "server_log_file") and cls.server_log_file:
            cls.server_log_file.close()
                
        # Clean test DB file
        test_db = Path("data/lend_test.db")
        if test_db.exists():
            try:
                test_db.unlink()
            except OSError:
                pass
                
        # Clean test mailbox
        mailbox_dir = Path("data/mailbox")
        if mailbox_dir.exists():
            shutil.rmtree(mailbox_dir, ignore_errors=True)

    def test_01_public_catalog_empty(self):
        """Verify the public catalog starts empty."""
        status, res = http_request("/api/books")
        self.assertEqual(status, 200)
        self.assertIn("books", res)
        self.assertEqual(len(res["books"]), 0)

    def test_02_access_control(self):
        """Verify that staff endpoints refuse unsigned-in actions."""
        # Try to add a book without token
        status, res = http_request("/api/books", method="POST", data={
            "title": "Unauthorized Book",
            "author": "No Name",
            "published_year": 2026,
            "isbn": "123-456"
        })
        self.assertEqual(status, 401)
        self.assertIn("error", res)

        # Try to add a member without token
        status, res = http_request("/api/members", method="POST", data={
            "name": "Unauthorized Member",
            "email": "member@test.com"
        })
        self.assertEqual(status, 401)

    def test_03_login_failure(self):
        """Verify login fails with bad credentials."""
        status, res = http_request("/api/auth/login", method="POST", data={
            "username": "admin",
            "password": "wrongpassword"
        })
        self.assertEqual(status, 401)
        self.assertIn("error", res)

    def test_04_login_success(self):
        """Verify login succeeds and issues a token."""
        status, res = http_request("/api/auth/login", method="POST", data={
            "username": "admin",
            "password": "staffpassword"
        })
        self.assertEqual(status, 200)
        self.assertIn("token", res)
        self.assertIn("staff", res)
        self.assertEqual(res["staff"]["username"], "admin")
        self.assertEqual(res["staff"]["name"], "Library Admin")
        
        # Save token for subsequent tests
        self.__class__.token = res["token"]

    def test_05_add_book_validation(self):
        """Verify input validation for adding books."""
        token = self.__class__.token
        
        # Missing title
        status, res = http_request("/api/books", method="POST", token=token, data={
            "author": "Author",
            "published_year": 2020,
            "isbn": "ISBN-1"
        })
        self.assertEqual(status, 400)
        self.assertIn("Title is required", res["message"])

        # Invalid year
        status, res = http_request("/api/books", method="POST", token=token, data={
            "title": "Title",
            "author": "Author",
            "published_year": 999,
            "isbn": "ISBN-1"
        })
        self.assertEqual(status, 400)
        self.assertIn("Published year must be between 1000 and 2100", res["message"])

    def test_06_add_book_success(self):
        """Verify adding books successfully."""
        token = self.__class__.token
        status, res = http_request("/api/books", method="POST", token=token, data={
            "title": "Introduction to Python",
            "author": "Guido van Rossum",
            "published_year": 2021,
            "isbn": "978-0134076430"
        })
        self.assertEqual(status, 201)
        self.assertIn("book_id", res)
        self.__class__.book_id = res["book_id"]

    def test_07_add_member_success(self):
        """Verify adding a member successfully."""
        token = self.__class__.token
        status, res = http_request("/api/members", method="POST", token=token, data={
            "name": "Jane Doe",
            "email": "jane.doe@example.com"
        })
        self.assertEqual(status, 201)
        self.assertIn("member_id", res)
        self.__class__.member_id = res["member_id"]

    def test_08_borrow_book_success(self):
        """Verify borrowing a book successfully."""
        token = self.__class__.token
        book_id = self.__class__.book_id
        member_id = self.__class__.member_id
        
        status, res = http_request("/api/loans", method="POST", token=token, data={
            "book_id": book_id,
            "member_id": member_id,
            "due_date": "2026-07-22"
        })
        self.assertEqual(status, 201)
        self.assertIn("loan_id", res)
        self.__class__.loan_id = res["loan_id"]

    def test_09_double_borrow_rejection(self):
        """Verify that a book out on loan cannot be borrowed again."""
        token = self.__class__.token
        book_id = self.__class__.book_id
        member_id = self.__class__.member_id
        
        status, res = http_request("/api/loans", method="POST", token=token, data={
            "book_id": book_id,
            "member_id": member_id,
            "due_date": "2026-07-30"
        })
        self.assertEqual(status, 409)
        self.assertIn("already out on loan", res["message"])

    def test_10_async_email_receipt(self):
        """Verify that the background worker captures the email receipt."""
        # Wait a moment for background task to run
        time.sleep(2)
        
        # DevMailbox captures outgoing emails in data/mailbox/outbox
        outbox_path = Path("data/mailbox/outbox")
        self.assertTrue(outbox_path.exists())
        
        emails = list(outbox_path.glob("*.json"))
        self.assertGreater(len(emails), 0)
        
        # Read the captured email
        with open(emails[0], "r", encoding="utf-8") as f:
            mail_data = json.load(f)
            
        self.assertIn("jane.doe@example.com", mail_data["to"])
        self.assertIn("Introduction to Python", mail_data["subject"])
        self.assertIn("2026-07-22", mail_data["body"])

    def test_11_return_book_success(self):
        """Verify returning a book successfully."""
        token = self.__class__.token
        loan_id = self.__class__.loan_id
        
        status, res = http_request(f"/api/loans/{loan_id}/return", method="POST", token=token)
        self.assertEqual(status, 200)

    def test_12_audit_logs(self):
        """Verify that staff actions are logged and attributed in audit log."""
        token = self.__class__.token
        status, res = http_request("/api/audit-logs", token=token)
        self.assertEqual(status, 200)
        
        # Should have log entries for add_book, add_member, record_loan, record_return
        actions = [log["action"] for log in res]
        self.assertIn("add_book", actions)
        self.assertIn("add_member", actions)
        self.assertIn("record_loan", actions)
        self.assertIn("record_return", actions)
        
        # Verify staff attribution
        for log in res:
            self.assertEqual(log["staff_id"], 1)
            self.assertEqual(log["staff_name"], "Library Admin")

if __name__ == "__main__":
    unittest.main()
